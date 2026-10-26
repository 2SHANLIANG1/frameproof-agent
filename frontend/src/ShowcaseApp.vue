<script setup>
import { computed, nextTick, onMounted, onScopeDispose, ref, watch } from 'vue'
import { defectLabels, formatTime, summaryText } from './lib/report.js'
import './showcase.css'
import './showcase-refresh.css'

const base = import.meta.env.BASE_URL
const cases = ref([])
const selectedId = ref('underwater')
const active = computed(() => cases.value.find(item => item.id === selectedId.value))
const player = ref(null)
const heroPlayer = ref(null)
const heroPlaying = ref(false)
const lightbox = ref(null)
const lightboxSource = ref('')
const workflowStep = ref(0)
let revealObserver
const currentTime = ref(0)
const tab = ref('frames')
const error = ref('')
const report = computed(() => active.value?.report)
const summary = computed(() => report.value?.summary)
const entities = computed(() => Object.entries(report.value?.memory.entity_cards || {}))
const steps = [
  ['输入与校验', '视频、生成提示词、镜头表与执行预算'],
  ['规则预检', '解码视频，检查黑帧、静音与元信息'],
  ['任务编译', '模型分解实体一致性与提示词要素任务'],
  ['局部取证', '圈选镜头，两组不同时间点静帧对照'],
  ['证据复核', '对照实体档案，整理确定与疑似问题'],
  ['报告交付', '汇总覆盖范围、时间戳与结构化证据'],
]
const stepDetails = [
  ['Vue 3 → Python API', '前端收集提示词、模式和预算，后端校验视频大小、时长与镜头边界。'],
  ['FFmpeg / qc.media', '真实解码视频，建立带时间戳的采帧网格；硬缺陷命中时提前报告。'],
  ['Ollama / Qwen3-VL', '在本地模型模式中，将生成要求拆成跨镜头一致性、要素符合度与缺陷子任务。'],
  ['Controller / probe', '控制器在预算内选择镜头，分别在镜头的 35% 与 65% 位置采样取证。'],
  ['QCMemory / recheck', '结合焦点缓存、实体属性和证据台账进行复核，区分确定与疑似候选。'],
  ['Report / JSON + TXT', '去重并补充时间戳，汇总检查覆盖与未完成范围，提供可下载的结构化报告。'],
]
async function toggleHero() {
  if (!heroPlayer.value) return
  if (heroPlayer.value.paused) {
    try { await heroPlayer.value.play() } catch { heroPlaying.value = false }
  } else heroPlayer.value.pause()
}
async function openGrid(source) {
  lightboxSource.value = source
  await nextTick()
  lightbox.value.showModal()
}
function asset(path) { return `${base}demo/${active.value.id}/${path}` }
function refresh() { window.location.reload() }
function jump(second) {
  if (!player.value) return
  player.value.currentTime = second
  player.value.pause()
  currentTime.value = second
  const bounds = player.value.getBoundingClientRect()
  if (bounds.top < 0 || bounds.bottom > window.innerHeight) {
    player.value.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' })
  }
}
function download(kind) {
  const data = kind === 'json' ? JSON.stringify(report.value, null, 2) : summaryText(report.value)
  const url = URL.createObjectURL(new Blob([data], { type: kind === 'json' ? 'application/json' : 'text/plain;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${active.value.id}-report.${kind}`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
watch(selectedId, () => { currentTime.value = 0; tab.value = 'frames' })
onMounted(async () => {
  try {
    const response = await fetch(`${base}demo/manifest.json`)
    if (!response.ok) throw new Error('示例资源加载失败，请刷新重试。')
    cases.value = await response.json()
    document.title = '视频质检项目 · 在线体验'
    await nextTick()
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      revealObserver = new IntersectionObserver(entries => {
        for (const entry of entries) if (entry.isIntersecting) {
          entry.target.classList.add('is-revealed')
          revealObserver.unobserve(entry.target)
        }
      }, { threshold: 0.08 })
      document.querySelectorAll('.show-evidence, .show-workflow, .show-demo').forEach(section => revealObserver.observe(section))
      if (!navigator.connection?.saveData) {
        try { await heroPlayer.value?.play() } catch { /* The preview remains available through its play button. */ }
      }
    }
  } catch (e) { error.value = e.message }
})
onScopeDispose(() => revealObserver?.disconnect())
</script>

<template>
  <header class="show-header"><a :href="base" class="show-name">视频质检工具 <span>项目演示</span></a><nav><a href="#demo">交互体验</a><a href="#evidence">取证依据</a><a href="#workflow">工作流程</a><a class="nav-source" href="https://github.com/2SHANLIANG1/frameproof-agent" target="_blank" rel="noopener">查看源码 <span>↗</span></a></nav></header>
  <main class="show-main">
    <section class="show-intro">
      <div class="hero-copy"><p class="show-eyebrow"><span class="edition-dot"/> VIDEO QUALITY / EVIDENCE FIRST</p><h1>每一帧，<br>都有据<span class="hero-emphasis">可查<svg viewBox="0 0 200 18" aria-hidden="true"><path d="M3 13Q97 1 196 10"/></svg></span>。</h1><p class="hero-description">从一段视频，到一份有依据的判断。<br>沿镜头寻找问题，用采样证据解释结论。</p><div class="hero-actions"><a class="hero-primary" href="#demo">开始体验 <span>↗</span></a><a class="hero-secondary" href="#workflow">了解它如何工作 <span>↓</span></a></div><div class="hero-stack"><span>Vue 3</span><i/> <span>Python</span><i/><span>Ollama · Qwen3-VL</span></div></div>
      <div class="hero-media"><video ref="heroPlayer" :src="`${base}demo/underwater/video.mp4`" :poster="`${base}demo/underwater/poster.jpg`" muted loop playsinline preload="metadata" aria-label="深海潜水示例视频的静音循环预览" @play="heroPlaying = true" @pause="heroPlaying = false"/><div class="hero-media-top"><span>示例片段 / 01</span><span>00:15</span></div><div class="hero-video-caption"><div><span>DEEP SEA / CASE STUDY</span><p>潜入光的深处。</p></div><button :aria-label="heroPlaying ? '暂停背景视频' : '播放背景视频'" @click="toggleHero">{{ heroPlaying ? 'Ⅱ' : '▶' }}</button></div><div v-if="cases.length" class="hero-proof"><span class="proof-icon">↗</span><div><b>不止看见，也能解释。</b><span>{{ cases[0].report.queue.length }} 项任务 · {{ cases[0].report.model_calls }} 次实际模型调用</span></div><a href="#evidence" @click="selectedId = 'underwater'" aria-label="查看潜水案例取证依据">→</a></div></div>
    </section>
    <div class="show-disclosure"><b><span/> 在线展示版</b><span>交互体验已完成的实际检测结果。此网页不上传视频、不调用模型；完整检测可下载源码在本机运行。</span><a href="#demo">探索案例 ↓</a></div>
    <p v-if="error" role="alert" class="show-error">{{ error }} <button @click="refresh">刷新</button></p>
    <p v-else-if="!active" role="status">正在加载示例视频与报告…</p>
    <template v-else>
      <section id="demo" class="show-demo">
        <div class="show-section-title"><div><p class="show-eyebrow">01 / THE EXPERIENCE</p><h2>先看画面。<span>再看依据。</span></h2></div><p>两个案例，两种结果。<br>点击镜头，把结论带回画面。</p></div>
        <div class="show-case-tabs" role="tablist" aria-label="演示案例"><button v-for="(item,index) in cases" :key="item.id" role="tab" :aria-selected="selectedId === item.id" :class="{active: selectedId === item.id}" @click="selectedId = item.id"><img :src="`${base}demo/${item.id}/poster.jpg`" alt=""><span class="case-label"><b>{{ item.label }}</b><span>{{ item.caption }}</span></span><span class="case-arrow">{{ selectedId === item.id ? '↘' : '↗' }}</span></button></div>
        <div :key="active.id" class="show-workspace">
          <section class="show-player-panel"><div class="show-panel-title"><h3>{{ active.meta.title }}</h3><span>{{ active.meta.duration_sec.toFixed(1) }} 秒 · {{ active.meta.shot_table.length }} 段</span></div><video :key="active.id" ref="player" :src="asset('video.mp4')" :poster="asset('poster.jpg')" controls playsinline preload="metadata" @timeupdate="currentTime = $event.target.currentTime" /><div class="show-timeline-label"><b>镜头时间轴</b><span>{{ formatTime(currentTime) }} / {{ formatTime(active.meta.duration_sec) }}</span></div><div class="show-timeline"><button v-for="(shot, index) in active.meta.shot_table" :key="shot.shot_id" :class="{selected: currentTime >= shot.t_start && currentTime < shot.t_end, issue: report.findings.some(f => f.shot_id === shot.shot_id)}" :title="`${shot.shot_id} · ${shot.t_start.toFixed(2)} 秒`" @click="jump(shot.t_start)"><img :src="asset(`shot-${index + 1}.jpg`)" alt="" loading="lazy"><span>{{ String(index + 1).padStart(2, '0') }}<small>{{ formatTime(shot.t_start) }}</small></span></button><i class="timeline-playhead" :style="{ left: `${Math.min(100, currentTime / active.meta.duration_sec * 100)}%` }"/></div><p class="show-small">点击片段跳转；{{ active.meta.synthetic ? '合成样例使用已知镜头表。' : '此示例按时长等分，不是自动镜头切分。' }}</p><details class="show-prompt" open><summary>生成提示词 / 检查要求</summary><p>{{ active.meta.prompt }}</p></details></section>
          <section class="show-conclusion"><p class="show-eyebrow">检测结果总结</p><h2>{{ summary.headline }}</h2><p>{{ summary.overview }}</p><div class="show-counts"><div><b>{{ summary.confirmed_count }}</b><span>确定缺陷</span></div><div><b>{{ summary.suspected_count }}</b><span>疑似问题</span></div><div><b>{{ summary.affected_shots.length }}</b><span>涉及镜头</span></div></div><div class="show-coverage"><b>检查覆盖</b><p>{{ summary.coverage_text }}</p></div><div class="show-result-actions"><a href="#evidence">查看取证依据 ↓</a><button @click="download('json')">导出 JSON</button><button @click="download('txt')">下载总结</button></div><dl class="show-run-details"><div><dt>运行方式</dt><dd>{{ report.model || '离线像素测量 / 合成样例' }}</dd></div><div><dt>实际耗时</dt><dd>{{ report.elapsed_sec.toFixed(1) }} 秒</dd></div><div><dt>模型调用</dt><dd>{{ report.model_calls }} 次</dd></div><div><dt>结果来源</dt><dd>{{ active.provenance }}</dd></div></dl></section>
        </div>
        <section v-if="report.findings.length" class="show-findings"><h3>定位检测到的问题</h3><article v-for="(finding, index) in report.findings" :key="index"><div><b>{{ defectLabels[finding.defect_type] || finding.defect_type }}</b><p>{{ finding.evidence }}</p><small>{{ finding.zone === 'confirmed' ? '确定缺陷' : '疑似问题' }} · {{ finding.source }}</small></div><button @click="jump(finding.timestamp)">{{ finding.shot_id }} · {{ formatTime(finding.timestamp) }} ↗</button></article></section>
      </section>
      <section id="evidence" class="show-evidence"><div class="show-section-title"><div><p class="show-eyebrow">02 / BEHIND THE RESULT</p><h2>让结论，<span>有迹可循。</span></h2></div><p>{{ report.sampled_frames }} 帧粗筛采样<br>{{ report.tokens?.toLocaleString() ?? '未知' }} Token · 来自实际运行</p></div><div class="show-evidence-tabs" role="tablist" aria-label="证据类型"><button v-for="(item,index) in [['frames','采样画面'],['entities','实体档案'],['ledger','证据台账'],['coverage','检查覆盖']]" :key="item[0]" role="tab" :aria-selected="tab === item[0]" :class="{active: tab === item[0]}" @click="tab = item[0]"><span>0{{ index+1 }}</span>{{ item[1] }}</button></div><div class="show-evidence-body">
        <div v-if="tab === 'frames'" class="show-grids"><button v-for="(grid,index) in report.memory.focus_cache.grids" :key="`${active.id}-${grid}`" class="grid-preview" @click="openGrid(asset(grid))"><img :src="asset(grid)" alt="实际视频解码产生的带时间戳采样网格" loading="lazy"><span>采样网格 0{{ index+1 }} <b>放大查看 ↗</b></span></button><p>{{ report.memory.focus_cache.sketch || '从实际视频解码采帧，用于检查和跨镜头对照。' }}</p></div>
        <div v-else-if="tab === 'entities'" class="show-entities"><article v-for="[name, entries] in entities" :key="name"><h3>{{ name }}</h3><div v-for="(entry, index) in entries" :key="index"><span>{{ entry.shot_id }}</span><span>{{ entry.value }}</span></div></article><p v-if="!entities.length">本次报告未记录实体属性。</p></div>
        <ol v-else-if="tab === 'ledger'" class="show-ledger"><li v-for="(entry,index) in report.memory.ledger" :key="index"><h3>{{ entry.step }} / {{ entry.action }}</h3><p>{{ entry.intent }}</p><details><summary>查看结构化证据</summary><pre>{{ JSON.stringify(entry.output, null, 2) }}</pre></details></li></ol>
        <div v-else class="show-coverage-list"><article v-for="(item,index) in report.coverage" :key="index"><h3>{{ item.task }} <span>{{ item.status }}</span></h3><p>{{ item.detail }}</p></article><p>{{ summary.note }}</p></div>
      </div></section>
    </template>
    <section id="workflow" class="show-workflow"><div class="show-section-title"><div><p class="show-eyebrow">03 / UNDER THE HOOD</p><h2>每一步，<span>都有来处。</span></h2></div></div><ol><li v-for="(step,index) in steps" :key="step[0]" :class="{active: workflowStep === index}"><button :aria-pressed="workflowStep === index" @click="workflowStep = index"><span>{{ String(index+1).padStart(2,'0') }} <i>↗</i></span><h3>{{ step[0] }}</h3><p>{{ step[1] }}</p></button></li></ol><div :key="workflowStep" class="workflow-detail"><span>0{{ workflowStep+1 }} / {{ stepDetails[workflowStep][0] }}</span><p>{{ stepDetails[workflowStep][1] }}</p></div><div class="show-engineering"><p><b>前端</b><span>Vue 3 组件、视频交互、进度轮询、报告与证据展示。</span></p><p><b>后端</b><span>Python API、FFmpeg 采帧、规则预检、模型调用与任务预算。</span></p><p><b>Agent</b><span>检查队列、焦点缓存、实体档案、证据台账及候选复核。</span></p></div></section>
    <footer class="show-footer"><p>个人视频质检演示项目 · 示例结果仅适用于标明的检查范围</p><a href="https://github.com/2SHANLIANG1/frameproof-agent#本地运行" target="_blank" rel="noopener">下载并运行完整程序 ↗</a></footer>
  </main>
  <dialog ref="lightbox" class="evidence-lightbox" @click="$event.target === lightbox && lightbox.close()"><div><p>实际采样证据 <button aria-label="关闭采样图片" @click="lightbox.close()">关闭 ×</button></p><img v-if="lightboxSource" :src="lightboxSource" alt="放大的带时间戳实际采样网格"></div></dialog>
</template>
