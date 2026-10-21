import test from 'node:test'
import assert from 'node:assert/strict'
import { effectScope } from 'vue'
import { useInspection } from '../src/composables/useInspection.js'
import { parseMetadata, summaryText, isRunId } from '../src/lib/report.js'

const runId = 'a'.repeat(32)
const video = { video_id: 'drift', title: '合成样例', synthetic: true, prompt: '米色外套', duration_sec: 12,
  shot_table: [{ shot_id: 'Shot #1', t_start: 0, t_end: 12 }] }
const report = { title: '测试报告', video_id: 'drift', input_prompt: '已存档的要求', mode: 'offline',
  shot_table: video.shot_table, findings: [], coverage: [],
  summary: { headline: '抽样检查完成', overview: '未检出缺陷', coverage_text: '仅采样画面',
    key_findings: [], next_action: '下载报告', note: '模型可能误判' } }

function session(t, respond, wait, videos = [video]) {
  const calls = []
  const scope = effectScope()
  const inspection = scope.run(() => useInspection({ wait, request: async (path, options) => {
    calls.push({ path, ...options })
    if (path === '/api/videos') return structuredClone(videos)
    if (path === '/api/health') return { local: true, live_ready: true, model: 'qwen3-vl:8b-instruct' }
    return respond(path, options)
  } }))
  t.after(() => scope.stop())
  return { inspection, scope, calls }
}

test('run sends edited prompt and metadata, polls progress and releases controls on completion', async t => {
  let polls = 0
  const { inspection: app, calls } = session(t, path => {
    if (path === '/api/runs') return { id: runId }
    if (++polls === 1) return { status: 'running', events: [{ title: '取证中', elapsed: 1 }] }
    return { status: 'done', report, events: [{ title: '完成', elapsed: 2 }] }
  }, async () => {})
  await app.initialize()
  assert.equal(app.state.mode, 'live')
  app.updatePrompt('  自定义检查要求  ')
  await app.runInspection()
  const start = calls.find(c => c.path === '/api/runs')
  assert.equal(start.data.metadata.prompt, '自定义检查要求')
  assert.equal(start.data.step_budget, 3)
  assert.equal(polls, 2)
  assert.equal(app.state.phase, 'done')
  assert.equal(app.state.busy, '')
  assert.equal(app.state.lastRun, runId)
  assert.ok(app.state.summaryUrl.startsWith('blob:'))
  app.selectVideo('drift')
  assert.equal(app.state.summaryUrl, '')
  assert.equal(app.state.report, null)
})

test('upload preserves a dirty prompt and opens the workspace', async t => {
  const { inspection: app, calls } = session(t, () => ({ ...video, video_id: 'upload1', synthetic: false, prompt: '' }))
  await app.initialize()
  app.updatePrompt('上传之前写好的要求')
  const file = new File(['video'], 'test.mp4', { type: 'video/mp4' })
  await app.uploadFile(file)
  assert.equal(app.state.prompt, '上传之前写好的要求')
  assert.equal(app.selected.value.video_id, 'upload1')
  assert.equal(app.state.workspaceOpen, true)
  assert.equal(app.state.busy, '')
  const upload = calls.find(c => c.path === '/api/upload')
  assert.equal(upload.raw, true)
  assert.equal(upload.data, file)
})

test('invalid JSON never starts a backend task', async t => {
  const { inspection: app, calls } = session(t, () => { throw new Error('must not request') })
  await app.initialize()
  app.state.metadataText = '[]'
  await app.runInspection()
  assert.match(app.state.toast, /JSON/)
  assert.ok(!calls.some(c => c.path === '/api/runs'))
})

test('model failure shows an error and restores input controls', async t => {
  const { inspection: app } = session(t, path => path === '/api/runs'
    ? { id: runId } : { status: 'error', error: '模型连接超时', events: [] })
  await app.initialize()
  await app.runInspection()
  assert.equal(app.state.phase, 'error')
  assert.equal(app.state.error, '模型连接超时')
  assert.equal(app.disabled.value, false)
  assert.equal(app.state.report, null)
})

test('disposing the Vue scope aborts a polling wait without a false failure', async t => {
  let reachedWait
  const waiting = new Promise(resolve => { reachedWait = resolve })
  const { inspection: app, scope } = session(t, path => path === '/api/runs'
    ? { id: runId } : { status: 'running', events: [] }, (ms, signal) => new Promise((resolve, reject) => {
      reachedWait()
      signal.addEventListener('abort', () => reject(signal.reason), { once: true })
    }))
  await app.initialize()
  const run = app.runInspection()
  await waiting
  scope.stop()
  await run
  assert.equal(app.state.error, '')
  assert.equal(app.state.busy, '')
})

test('history restoration uses archived prompt, shot table and execution mode', async t => {
  const previous = globalThis.location
  globalThis.location = { search: '?run=' + runId, hash: '' }
  t.after(() => { if (previous === undefined) delete globalThis.location; else globalThis.location = previous })
  const { inspection: app } = session(t, () => ({ status: 'done', report, events: [] }))
  await app.initialize()
  assert.equal(app.state.mode, 'offline')
  assert.equal(app.state.prompt, '已存档的要求')
  assert.equal(app.state.run, runId)
  assert.equal(app.state.workspaceOpen, true)
  assert.equal(app.reportHref.value, `/?run=${runId}#report`)
})

test('report text preserves evidence without inventing conclusions', () => {
  assert.match(summaryText(report), /仅采样画面/)
  assert.match(summaryText(report), /模型可能误判/)
  assert.deepEqual(parseMetadata('{"shot_table":[]}', ' 要求 '), { shot_table: [], prompt: '要求' })
  assert.equal(isRunId('../.env'), false)
})

test('homepage and sample button prefer the configured example over synthetic fixtures', async t => {
  const underwater = { ...video, video_id: 'underwater', synthetic: false,
    example: true, default_example: true, title: '深海潜水', prompt: '深海潜水员与发光水母' }
  const { inspection: app } = session(t, () => {}, undefined, [video, underwater])
  await app.initialize()
  assert.equal(app.state.selectedId, 'underwater')
  assert.equal(app.state.prompt, underwater.prompt)
  assert.equal(app.selected.value.synthetic, false)
  app.selectVideo('drift')
  app.chooseSample()
  assert.equal(app.state.selectedId, 'underwater')
  assert.equal(app.state.prompt, underwater.prompt)
  assert.equal(app.state.workspaceOpen, true)
})
