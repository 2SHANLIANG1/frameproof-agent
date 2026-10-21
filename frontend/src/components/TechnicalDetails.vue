<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useInspectionContext } from '../composables/useInspection.js'
const { state, reportVisible } = useInspectionContext()
const eventsElement = ref(null)
const cards = computed(() => Object.entries(state.report?.memory.entity_cards || {}))
const focus = computed(() => state.report?.memory.focus_cache || {})
const tabs = [{ id: 'focus', label: '采样画面' }, { id: 'entities', label: '实体档案' }, { id: 'ledger', label: '证据台账' }]
watch(() => state.events.length, async () => {
  await nextTick()
  if (eventsElement.value) eventsElement.value.scrollTop = eventsElement.value.scrollHeight
})
</script>

<template>
  <details v-if="reportVisible || state.showTechnical" id="technical" class="technical" :open="state.technicalOpen" @toggle="state.technicalOpen = $event.target.open">
    <summary><span>检测过程与技术详情</span><span>查看调用轨迹、用量与证据台账</span></summary>
    <section class="metrics">
      <div><span>检查维度</span><strong>3 <small>一致性 / 符合度 / 缺陷</small></strong></div>
      <div><span>粗筛采样帧</span><strong id="metric-frames">{{ state.report?.sampled_frames ?? '—' }}<small>{{ state.report ? '真实抽取的粗筛帧' : '按区间自适应' }}</small></strong></div>
      <div><span>模型 Token</span><strong id="metric-tokens">{{ state.report ? state.report.tokens === null ? '未知' : state.report.tokens.toLocaleString() : state.mode === 'live' ? '—' : '0' }}<small>{{ state.report ? state.report.mode === 'offline' ? '无模型调用' : `${state.report.model_calls} 次实际模型调用` : '等待检查' }}</small></strong></div>
      <div><span>处理耗时</span><strong id="metric-time">{{ state.report ? state.report.elapsed_sec.toFixed(1) : '—' }}<small>{{ state.report ? '秒 / 本机实测' : '等待开始' }}</small></strong></div>
    </section>
    <section id="process" class="panel process-panel">
      <div class="panel-title"><h2>取证轨迹</h2><span id="process-state" class="pill" role="status">{{ state.processState }}</span></div>
      <div class="pipeline"><span>检查项编译</span><b>→</b><span>规则预检</span><b>→</b><span>镜头圈选</span><b>→</b><span>视觉取证</span><b>→</b><span>独立复核</span><b>→</b><span>诊断报告</span></div>
      <div id="events" ref="eventsElement" class="events">
        <div v-for="(event, index) in state.events" :key="index" class="event"><span class="event-time">{{ event.elapsed.toFixed(1) }}s</span><span class="event-dot" /><div>{{ event.title }}<p>{{ event.detail }}</p></div></div>
        <div v-if="!state.events.length" class="empty"><p>{{ state.report ? '历史报告保留的取证证据可在下方台账查看。' : '启动质检后显示工具调用与证据归档。' }}</p></div>
      </div>
    </section>
    <section id="memory" class="panel memory-panel">
      <div class="panel-title"><h2>证据与记忆</h2><span class="subtle">原始图像不进入文本历史</span></div>
      <div class="tabs" role="tablist" aria-label="证据类型"><button v-for="tab in tabs" :key="tab.id" :id="`tab-${tab.id}`" class="tab" :class="{active: state.tab === tab.id}" :data-tab="tab.id" role="tab" :aria-selected="state.tab === tab.id" aria-controls="memory-content" @click="state.tab = tab.id">{{ tab.label }}</button></div>
      <div id="memory-content" role="tabpanel" :aria-labelledby="`tab-${state.tab}`">
        <div v-if="!state.report" class="empty"><p>检测后可查看采样画面、实体档案和证据台账。</p></div>
        <template v-else-if="state.tab === 'focus'">
          <img v-for="grid in focus.grids || []" :key="grid" class="grid-img" alt="带时间戳的真实采帧网格" :src="`/artifacts/${state.run}/${encodeURIComponent(grid)}`" loading="lazy">
          <p class="memory-caption">{{ focus.num_frames || 0 }} 帧 · 仅保留最近的圈选焦点。探针缓冲已清空。</p>
        </template>
        <template v-else-if="state.tab === 'entities'">
          <div v-for="[key, values] in cards" :key="key" class="entity-card"><b>{{ key }}</b><p class="memory-caption">{{ new Set(values.map(v => v.value)).size > 1 ? '检测到属性冲突' : '当前观测一致' }}</p><div v-for="(entry, index) in values" :key="index" class="entity-row" :class="{conflict: entry.value === '蓝色外套'}"><span>{{ entry.shot_id }}</span><span>{{ entry.value }}</span></div></div>
          <p v-if="!cards.length" class="memory-caption">此运行没有实体属性观测，模型证据可在台账中查看。</p>
        </template>
        <pre v-else>{{ JSON.stringify(state.report.memory.ledger, null, 2) }}</pre>
      </div>
    </section>
  </details>
</template>
