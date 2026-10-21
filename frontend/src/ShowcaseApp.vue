<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { defectLabels, formatTime, summaryText } from './lib/report.js'
import './showcase.css'

const base = import.meta.env.BASE_URL
const cases = ref([])
const selectedId = ref('underwater')
const active = computed(() => cases.value.find(item => item.id === selectedId.value))
const player = ref(null)
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
function asset(path) { return `${base}demo/${active.value.id}/${path}` }
function refresh() { window.location.reload() }
function jump(second) {
  if (!player.value) return
  player.value.currentTime = second
  player.value.pause()
  currentTime.value = second
  const bounds = player.value.getBoundingClientRect()
  if (bounds.top < 0 || bounds.bottom > window.innerHeight) {
    player.value.scrollIntoView({ behavior: 'smooth', block: 'center' })
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
  } catch (e) { error.value = e.message }
})
</script>

<template>
  <header class="show-header"><a :href="base" class="show-name">视频质检工具 <span>项目演示</span></a><nav><a href="#demo">体验报告</a><a href="#workflow">工作流程</a><a href="https://github.com/2SHANLIANG1/frameproof-agent" target="_blank" rel="noopener">查看源码 ↗</a></nav></header>
  <main class="show-main">
    <section class="show-intro"><p class="show-eyebrow">Vue 3 / Python / Ollama</p><h1>看一段视频，读懂一次质检。</h1><p>播放示例视频，沿时间轴定位镜头，再对照模型的采样证据与检测结论。</p><div class="show-disclosure"><b>在线展示版</b><span>报告来自已完成的实际运行。此网页不上传视频、不调用模型；完整检测可下载源码在本机运行。</span></div></section>
    <p v-if="error" role="alert" class="show-error">{{ error }} <button @click="refresh">刷新</button></p>
    <p v-else-if="!active" role="status">正在加载示例视频与报告…</p>
    <template v-else>
      <section id="demo" class="show-demo">
        <div class="show-section-title"><div><p class="show-eyebrow">01 / 交互体验</p><h2>选择一个案例</h2></div><span>无需安装 · 点击即可查看</span></div>
        <div class="show-case-tabs" role="tablist" aria-label="演示案例"><button v-for="item in cases" :key="item.id" role="tab" :aria-selected="selectedId === item.id" :class="{active: selectedId === item.id}" @click="selectedId = item.id"><b>{{ item.label }}</b><span>{{ item.caption }}</span></button></div>
        <div class="show-workspace">
          <section class="show-player-panel"><div class="show-panel-title"><h3>{{ active.meta.title }}</h3><span>{{ active.meta.duration_sec.toFixed(1) }} 秒 · {{ active.meta.shot_table.length }} 段</span></div><video :key="active.id" ref="player" :src="asset('video.mp4')" :poster="asset('poster.jpg')" controls playsinline preload="metadata" @timeupdate="currentTime = $event.target.currentTime" /><div class="show-timeline-label"><b>镜头时间轴</b><span>{{ formatTime(currentTime) }} / {{ formatTime(active.meta.duration_sec) }}</span></div><div class="show-timeline"><button v-for="(shot, index) in active.meta.shot_table" :key="shot.shot_id" :class="{selected: currentTime >= shot.t_start && currentTime < shot.t_end, issue: report.findings.some(f => f.shot_id === shot.shot_id)}" :title="`${shot.shot_id} · ${shot.t_start.toFixed(2)} 秒`" @click="jump(shot.t_start)">{{ String(index + 1).padStart(2, '0') }}</button></div><p class="show-small">点击片段跳转；{{ active.meta.synthetic ? '合成样例使用已知镜头表。' : '此示例按时长等分，不是自动镜头切分。' }}</p><details class="show-prompt" open><summary>生成提示词 / 检查要求</summary><p>{{ active.meta.prompt }}</p></details></section>
          <section class="show-conclusion"><p class="show-eyebrow">检测结果总结</p><h2>{{ summary.headline }}</h2><p>{{ summary.overview }}</p><div class="show-counts"><div><b>{{ summary.confirmed_count }}</b><span>确定缺陷</span></div><div><b>{{ summary.suspected_count }}</b><span>疑似问题</span></div><div><b>{{ summary.affected_shots.length }}</b><span>涉及镜头</span></div></div><div class="show-coverage"><b>检查覆盖</b><p>{{ summary.coverage_text }}</p></div><div class="show-result-actions"><a href="#evidence">查看取证依据 ↓</a><button @click="download('json')">导出 JSON</button><button @click="download('txt')">下载总结</button></div><dl class="show-run-details"><div><dt>运行方式</dt><dd>{{ report.model || '离线像素测量 / 合成样例' }}</dd></div><div><dt>实际耗时</dt><dd>{{ report.elapsed_sec.toFixed(1) }} 秒</dd></div><div><dt>模型调用</dt><dd>{{ report.model_calls }} 次</dd></div><div><dt>结果来源</dt><dd>{{ active.provenance }}</dd></div></dl></section>
        </div>
        <section v-if="report.findings.length" class="show-findings"><h3>定位检测到的问题</h3><article v-for="(finding, index) in report.findings" :key="index"><div><b>{{ defectLabels[finding.defect_type] || finding.defect_type }}</b><p>{{ finding.evidence }}</p><small>{{ finding.zone === 'confirmed' ? '确定缺陷' : '疑似问题' }} · {{ finding.source }}</small></div><button @click="jump(finding.timestamp)">{{ finding.shot_id }} · {{ formatTime(finding.timestamp) }} ↗</button></article></section>
      </section>
      <section id="evidence" class="show-evidence"><div class="show-section-title"><div><p class="show-eyebrow">02 / 证据可追溯</p><h2>结论依据，展开来看。</h2></div><span>{{ report.sampled_frames }} 帧粗筛采样 · {{ report.tokens?.toLocaleString() ?? '未知' }} Token</span></div><div class="show-evidence-tabs" role="tablist" aria-label="证据类型"><button v-for="item in [['frames','采样画面'],['entities','实体档案'],['ledger','证据台账'],['coverage','检查覆盖']]" :key="item[0]" role="tab" :aria-selected="tab === item[0]" :class="{active: tab === item[0]}" @click="tab = item[0]">{{ item[1] }}</button></div><div class="show-evidence-body">
        <div v-if="tab === 'frames'" class="show-grids"><img v-for="grid in report.memory.focus_cache.grids" :key="`${active.id}-${grid}`" :src="asset(grid)" alt="实际视频解码产生的带时间戳采样网格" loading="lazy"><p>{{ report.memory.focus_cache.sketch || '从实际视频解码采帧，用于检查和跨镜头对照。' }}</p></div>
        <div v-else-if="tab === 'entities'" class="show-entities"><article v-for="[name, entries] in entities" :key="name"><h3>{{ name }}</h3><div v-for="(entry, index) in entries" :key="index"><span>{{ entry.shot_id }}</span><span>{{ entry.value }}</span></div></article><p v-if="!entities.length">本次报告未记录实体属性。</p></div>
        <ol v-else-if="tab === 'ledger'" class="show-ledger"><li v-for="(entry,index) in report.memory.ledger" :key="index"><h3>{{ entry.step }} / {{ entry.action }}</h3><p>{{ entry.intent }}</p><details><summary>查看结构化证据</summary><pre>{{ JSON.stringify(entry.output, null, 2) }}</pre></details></li></ol>
        <div v-else class="show-coverage-list"><article v-for="(item,index) in report.coverage" :key="index"><h3>{{ item.task }} <span>{{ item.status }}</span></h3><p>{{ item.detail }}</p></article><p>{{ summary.note }}</p></div>
      </div></section>
    </template>
    <section id="workflow" class="show-workflow"><div class="show-section-title"><div><p class="show-eyebrow">03 / 项目实现</p><h2>从输入到可核查的报告</h2></div><a href="https://github.com/2SHANLIANG1/frameproof-agent/blob/main/docs/WORKFLOW.md" target="_blank" rel="noopener">查看完整流程图 ↗</a></div><ol><li v-for="(step,index) in steps" :key="step[0]"><span>{{ String(index+1).padStart(2,'0') }}</span><h3>{{ step[0] }}</h3><p>{{ step[1] }}</p></li></ol><div class="show-engineering"><p><b>前端：</b>Vue 3 组件、视频交互、进度轮询、报告与证据展示。</p><p><b>后端：</b>Python API、FFmpeg 采帧、规则预检、模型调用与任务预算。</p><p><b>Agent：</b>检查队列、焦点缓存、实体档案、证据台账及候选复核。</p></div></section>
    <footer class="show-footer"><p>个人视频质检演示项目 · 示例结果仅适用于标明的检查范围</p><a href="https://github.com/2SHANLIANG1/frameproof-agent#快速启动" target="_blank" rel="noopener">下载并运行完整程序 ↗</a></footer>
  </main>
</template>
