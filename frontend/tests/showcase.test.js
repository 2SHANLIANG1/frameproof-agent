import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import createConfig from '../vite.config.js'

const fixtureRoot = new URL('../../showcase/public/demo/', import.meta.url)
const manifest = JSON.parse(readFileSync(new URL('manifest.json', fixtureRoot), 'utf8'))

test('published showcase cases have usable video, evidence, timed findings and explicit provenance', () => {
  assert.deepEqual(manifest.map(item => item.id), ['underwater', 'drift'])
  for (const item of manifest) {
    assert.ok(item.provenance)
    assert.ok(item.report.summary.headline)
    assert.equal(item.report.video_id, item.id)
    assert.equal(item.report.shot_table.length, item.meta.shot_table.length)
    for (const filename of ['video.mp4', 'poster.jpg', ...item.meta.shot_table.map((_,index) => `shot-${index+1}.jpg`), ...item.report.memory.focus_cache.grids]) {
      assert.ok(existsSync(new URL(`${item.id}/${filename}`, fixtureRoot)), `${item.id}/${filename}`)
    }
    for (const finding of item.report.findings) {
      assert.ok(item.meta.shot_table.some(shot => shot.shot_id === finding.shot_id))
      assert.ok(finding.timestamp >= 0 && finding.timestamp < item.meta.duration_sec)
    }
  }
  assert.equal(manifest[0].report.provider, 'ollama')
  assert.equal(manifest[0].report.model_calls, 65)
  assert.equal(manifest[1].report.model_calls, 0)
  assert.ok(manifest[1].report.findings.some(f => f.shot_id === 'Shot #4'))
})

test('showcase build uses repository subpath and separate assets; local backend build stays intact', () => {
  const online = createConfig({ mode: 'showcase' })
  const local = createConfig({ mode: 'production' })
  assert.equal(online.base, '/frameproof-agent/')
  assert.equal(local.base, '/')
  assert.equal(online.publicDir, fileURLToPath(new URL('../../showcase/public', import.meta.url)))
  assert.notEqual(online.build.outDir, local.build.outDir)
  const published = JSON.stringify(manifest)
  assert.doesNotMatch(published, /(?:[CD]:\\|QC_API_KEY|wxid_|127\.0\.0\.1)/i)
})
