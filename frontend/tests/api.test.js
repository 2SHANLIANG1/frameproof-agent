import test from 'node:test'
import assert from 'node:assert/strict'
import { api, pause } from '../src/lib/api.js'

test('API writes preserve the local server header and raw upload body', async t => {
  const received = []
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    received.push({ path, ...options })
    return new Response('{"ok":true}', { status: 200 })
  })
  await api('/api/runs', { data: { video_id: 'drift' } })
  const file = new Blob(['video'])
  await api('/api/upload', { data: file, raw: true })
  assert.equal(received[0].headers['X-FrameProof'], '1')
  assert.equal(received[0].headers['Content-Type'], 'application/json')
  assert.equal(JSON.parse(received[0].body).video_id, 'drift')
  assert.equal(received[1].body, file)
  assert.equal(received[1].headers['Content-Type'], undefined)
})

test('backend errors and non-JSON responses become useful errors', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => new Response('{"error":"请稍后重试"}', { status: 429 }))
  await assert.rejects(api('/api/runs'), /请稍后重试/)
  fetch.mock.mockImplementation(async () => new Response('<html>error</html>', { status: 502 }))
  await assert.rejects(api('/api/runs'), /HTTP 502/)
})

test('poll delays stop immediately when a component is disposed', async () => {
  const controller = new AbortController()
  const pending = pause(60000, controller.signal)
  controller.abort()
  await assert.rejects(pending, { name: 'AbortError' })
})
