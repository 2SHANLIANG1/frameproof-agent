export const defectLabels = {
  character_appearance_drift: '角色外观漂移', scene_prop_inconsistency: '场景或道具不一致',
  physical_anomaly: '画面物理异常', prompt_deviation: '提示词偏离', black_frame: '黑帧',
  silent_segment: '静音片段', resolution_anomaly: '分辨率异常', shot_table_mismatch: '镜头表错位',
}
export const isRunId = value => typeof value === 'string' && /^[a-f0-9]{32}$/.test(value)
export function formatTime(seconds = 0) {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
}
export function summaryText(report) {
  const s = report.summary
  if (!s) return ''
  return [report.title, s.headline, s.overview, '检查覆盖：' + s.coverage_text,
    ...s.key_findings.map(f => `${f.shot_id} · ${f.label}${f.zone === 'suspected' ? '（疑似）' : ''}：${f.evidence}`),
    '建议处理：' + s.next_action, s.note].join('\n\n')
}
export function parseMetadata(text, prompt) {
  let data
  try { data = JSON.parse(text) } catch { throw new Error('高级设置中的镜头表 JSON 格式无效') }
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('高级设置中的镜头表 JSON 格式无效')
  return { ...data, prompt: prompt.trim() }
}
