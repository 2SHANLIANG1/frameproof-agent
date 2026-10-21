import { computed, inject, nextTick, onScopeDispose, reactive, watch } from 'vue'
import { api, pause } from '../lib/api.js'
import { isRunId, parseMetadata, summaryText } from '../lib/report.js'

export const inspectionKey = Symbol('inspection')
export function useInspectionContext() {
  const context = inject(inspectionKey)
  if (!context) throw new Error('Inspection context is missing')
  return context
}

// One application-scoped session. Components consume reactive state and actions,
// while requests, polling and object URL lifetimes are managed here.
export function useInspection({ request = api, wait = pause } = {}) {
  const controller = new AbortController()
  let toastTimer
  const state = reactive({
    videos: [], selectedId: '', prompt: '', promptDirty: false, metadataText: '',
    mode: 'offline', budget: 8, backend: null, initializing: true, busy: '',
    workspaceOpen: false, technicalOpen: false, showTechnical: false,
    run: null, report: null, currentShots: [], events: [], phase: 'idle',
    processState: '等待任务', runStatus: '就绪 · 仅在本机处理', uploadStatus: '',
    error: '', toast: '', summaryUrl: '', tab: 'focus', feedback: '', feedbackStatus: '',
    lastRun: '', activeSecond: null,
  })
  const selected = computed(() => state.videos.find(v => v.video_id === state.selectedId))
  const defaultVideo = computed(() => state.videos.find(v => v.default_example)
    || state.videos.find(v => v.video_id === 'drift') || state.videos[0])
  const shots = computed(() => state.currentShots.length ? state.currentShots : selected.value?.shot_table || [])
  const disabled = computed(() => state.initializing || Boolean(state.busy))
  const summary = computed(() => state.report?.summary)
  const isClear = computed(() => ['sampled_clear', 'checked_clear'].includes(summary.value?.outcome))
  const reportVisible = computed(() => state.phase !== 'idle' || Boolean(state.report))
  const reportHref = computed(() => state.lastRun ? `/?run=${state.lastRun}#report` : '#report')
  const modeDescription = computed(() => state.mode === 'live'
    ? state.backend?.local
      ? `本机 Ollama · ${state.backend.model || '待配置'}。抽样帧在本机推理，无需 API Key；首次加载稍慢。`
      : '视频抽样帧将发送至你配置的模型服务；调用会产生服务商费用。'
    : '采帧与规则真实运行；合成色块用于演示跨镜头取证。')
  const modelOption = computed(() => state.backend?.local
    ? `本机 Ollama · ${state.backend.model || '待配置'}`
    : state.backend?.live_ready ? '真实视觉模型' : '真实视觉模型 · 请先配置 .env')
  const call = (path, options = {}) => request(path, { ...options, signal: controller.signal })

  function toast(message) {
    state.toast = message
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { state.toast = '' }, 6000)
  }
  async function scrollTo(id) {
    await nextTick()
    if (!controller.signal.aborted && typeof document !== 'undefined') {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }
  function clearReport() {
    Object.assign(state, { run: null, report: null, currentShots: [], events: [], phase: 'idle',
      feedback: '', feedbackStatus: '', error: '', activeSecond: null,
      processState: '等待任务', runStatus: '就绪 · 仅在本机处理' })
  }
  function selectVideo(id) {
    const video = state.videos.find(v => v.video_id === id)
    if (!video) return
    clearReport()
    state.selectedId = id
    state.prompt = video.prompt || ''
    state.promptDirty = false
    state.metadataText = JSON.stringify({ shot_table: video.shot_table,
      ...(video.gen_params && { gen_params: video.gen_params }) }, null, 2)
    state.uploadStatus = video.example ? `当前示例：${video.title}` : video.synthetic ? '未上传本地视频，当前使用内置样例。'
      : `已选择：${video.original_filename || video.title}`
  }
  function updatePrompt(value) { state.prompt = value; state.promptDirty = true }
  function openWorkspace() { state.workspaceOpen = true; scrollTo('workspace') }
  function chooseSample() { if (!disabled.value) { selectVideo(defaultVideo.value?.video_id); openWorkspace() } }
  function openTechnical() { state.showTechnical = true; state.technicalOpen = true; scrollTo('technical') }

  async function uploadFile(file) {
    if (!file || disabled.value) return
    if (file.size > 60 * 1024 * 1024) return toast('文件不能超过 60 MB')
    const draft = state.promptDirty ? state.prompt : null
    state.busy = 'upload'
    state.uploadStatus = `正在上传：${file.name}`
    state.runStatus = '正在上传并验证视频…'
    try {
      const meta = await call('/api/upload', { data: file, raw: true })
      meta.original_filename = file.name
      state.videos.push(meta)
      selectVideo(meta.video_id)
      if (draft !== null) updatePrompt(draft)
      openWorkspace()
      toast('视频已上传，请填写提示词或检查要求，然后开始质检。')
    } catch (error) {
      if (!controller.signal.aborted) {
        state.uploadStatus = '上传失败：' + error.message
        state.runStatus = error.message
        toast(error.message)
      }
    } finally { state.busy = '' }
  }

  function applyReport(report, runId) {
    state.run = runId
    state.report = report
    state.currentShots = report.shot_table || selected.value?.shot_table || []
    state.phase = 'done'
    state.workspaceOpen = true
  }
  async function runInspection() {
    if (disabled.value || !selected.value) return
    let metadata
    try { metadata = parseMetadata(state.metadataText, state.prompt) }
    catch (error) { return toast(error.message) }
    clearReport()
    Object.assign(state, { busy: 'inspection', phase: 'running', technicalOpen: true,
      processState: '运行中', runStatus: '正在分析，请稍候…', currentShots: metadata.shot_table || [] })
    try {
      const job = await call('/api/runs', { data: { video_id: state.selectedId, mode: state.mode,
        step_budget: Number(state.budget), metadata } })
      state.run = job.id
      while (!controller.signal.aborted) {
        const result = await call('/api/runs/' + job.id)
        state.events = result.events || []
        if (result.status === 'error') throw new Error(result.error || '检测失败')
        if (result.status === 'done') {
          applyReport(result.report, job.id)
          state.lastRun = job.id
          try {
            localStorage.setItem('frameproof.lastRun', job.id)
            history.replaceState(null, '', `${location.pathname}?run=${job.id}#report`)
          } catch { /* Browser storage may be disabled. The report remains usable. */ }
          state.processState = '已完成'
          state.runStatus = '质检完成 · 报告已保存'
          scrollTo('report')
          break
        }
        await wait(650, controller.signal)
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        Object.assign(state, { phase: 'error', error: error.message, processState: '处理失败', runStatus: error.message })
        toast(error.message)
      }
    } finally { state.busy = '' }
  }
  async function saveFeedback() {
    if (!state.run || !state.report) return
    try {
      await call('/api/feedback', { data: { run_id: state.run, note: state.feedback } })
      state.feedbackStatus = '已保存至本地复核库；不会自动纳入评测集。'
      state.feedback = ''
    } catch (error) { if (!controller.signal.aborted) toast(error.message) }
  }
  async function initialize() {
    try {
      state.videos = await call('/api/videos')
      selectVideo(defaultVideo.value?.video_id)
      state.backend = await call('/api/health')
      if (state.backend.local && state.backend.live_ready) { state.mode = 'live'; state.budget = 3 }
      state.runStatus = state.backend.live_ready ? '就绪 · 模型可用' : state.backend.detail || state.runStatus
      try {
        const last = localStorage.getItem('frameproof.lastRun')
        if (isRunId(last)) state.lastRun = last
      } catch { /* Optional browser history shortcut. */ }
      const savedRun = new URLSearchParams(globalThis.location?.search || '').get('run')
      if (isRunId(savedRun)) {
        try {
          const job = await call('/api/runs/' + savedRun)
          if (job.status === 'done') {
            const report = job.report
            selectVideo(report.video_id)
            applyReport(report, savedRun)
            state.lastRun = savedRun
            state.mode = report.mode || state.mode
            state.metadataText = JSON.stringify({ ...JSON.parse(state.metadataText), shot_table: state.currentShots }, null, 2)
            state.prompt = report.input_prompt ?? state.prompt
            state.events = job.events || []
            state.processState = '历史报告'
            state.runStatus = '已恢复上次完成的报告'
            if (globalThis.location?.hash === '#report') scrollTo('report')
          } else toast('该任务尚未完成，请稍后重新打开报告。')
        } catch (error) { if (!controller.signal.aborted) toast('历史报告未找到，可重新开始质检。') }
      }
    } catch (error) { if (!controller.signal.aborted) { state.runStatus = '初始化失败，可刷新页面重试'; toast(error.message) } }
    finally { state.initializing = false }
  }
  watch(() => state.report, report => {
    if (state.summaryUrl) URL.revokeObjectURL(state.summaryUrl)
    state.summaryUrl = report?.summary ? URL.createObjectURL(new Blob([summaryText(report)], { type: 'text/plain;charset=utf-8' })) : ''
  }, { flush: 'sync' })
  onScopeDispose(() => {
    controller.abort()
    clearTimeout(toastTimer)
    if (state.summaryUrl) URL.revokeObjectURL(state.summaryUrl)
  })
  return { state, selected, shots, disabled, summary, isClear, reportVisible, reportHref, modeDescription,
    modelOption, initialize, selectVideo, updatePrompt, chooseSample, openWorkspace, openTechnical,
    uploadFile, runInspection, saveFeedback }
}
