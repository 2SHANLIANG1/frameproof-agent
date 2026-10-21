import test from 'node:test'
import assert from 'node:assert/strict'
import createConfig from '../vite.config.js'
const config = createConfig({ mode: 'development' })

test('development proxy rewrites only its own local origins, preserving foreign-origin rejection', () => {
  const proxy = config.server.proxy['/api']
  let forward
  proxy.configure({ on(event, handler) { assert.equal(event, 'proxyReq'); forward = handler } })
  for (const origin of ['http://127.0.0.1:5173', 'http://localhost:5173', 'https://foreign.example', undefined]) {
    const headers = {}
    forward({ setHeader(key, value) { headers[key] = value } }, { headers: { origin } })
    assert.equal(headers.Origin, origin?.includes(':5173') ? 'http://127.0.0.1:8765' : undefined)
  }
})
