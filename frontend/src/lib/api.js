export async function api(path, { data, raw = false, signal } = {}) {
  const response = await fetch(path, {
    signal,
    ...(data !== undefined && {
      method: 'POST',
      headers: { 'X-FrameProof': '1', ...(!raw && { 'Content-Type': 'application/json' }) },
      body: raw ? data : JSON.stringify(data),
    }),
  })
  let result
  try {
    result = await response.json()
  } catch {
    throw new Error(`服务返回了无法解析的响应（HTTP ${response.status}）`)
  }
  if (!response.ok) throw new Error(result.error || `请求失败（HTTP ${response.status}）`)
  return result
}

export function pause(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(signal.reason)
    const abort = () => { clearTimeout(timer); reject(signal.reason) }
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, ms)
    signal.addEventListener('abort', abort, { once: true })
  })
}
