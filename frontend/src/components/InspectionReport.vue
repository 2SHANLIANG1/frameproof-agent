<script setup>
import { computed } from 'vue'
import { useInspectionContext } from '../composables/useInspection.js'
import { defectLabels } from '../lib/report.js'
const emit = defineEmits(['jump'])
const { state, summary, isClear, reportVisible, saveFeedback } = useInspectionContext()
const confirmedCount = computed(() => state.report?.findings.filter(f => f.zone === 'confirmed').length || 0)
const fallbackLabel = computed(() => ({ fail: '发现确定缺陷', needs_review: '检查不充分 · 请查看覆盖详情', pass: '已检查项目通过' })[state.report?.status])
</script>

<template>
  <section v-if="reportVisible" id="report" class="panel summary-panel" aria-live="polite">
    <div class="panel-title"><h2>检测结果总结</h2><a v-if="state.summaryUrl" id="download-summary" class="download" :href="state.summaryUrl" download="frameproof-summary.txt">下载文字总结 ↗</a></div>
    <div id="summary-content">
      <template v-if="summary">
        <h3 class="summary-heading">{{ summary.headline }}</h3><p class="summary-overview">{{ summary.overview }}</p>
        <div class="summary-stats"><div class="summary-stat"><b>{{ summary.confirmed_count }}</b>项确定缺陷</div><div class="summary-stat"><b>{{ summary.suspected_count }}</b>项疑似问题</div><div class="summary-stat"><b>{{ summary.affected_shots.length }}</b>个涉及镜头</div></div>
        <div class="summary-note" :class="{ clear: isClear }"><b>检查覆盖：</b>{{ summary.coverage_text }}</div>
        <div v-if="summary.key_findings.length" class="summary-key"><b>主要证据</b><p v-for="(finding, index) in summary.key_findings" :key="index">{{ finding.shot_id }} · {{ finding.label }}{{ finding.zone === 'suspected' ? '（疑似）' : '' }}：{{ finding.evidence }}</p></div>
        <div class="summary-action"><b>建议处理：</b>{{ summary.next_action }}</div>
        <p class="summary-source">{{ state.report.title }} · {{ state.report.model || '离线演示' }} · 运行 {{ state.run?.slice(0, 8) }}<br>{{ summary.note }} 输入修改后请重新质检。</p>
      </template>
      <p v-else-if="state.phase === 'error'" class="summary-note">本次检测失败，尚未生成总结：{{ state.error }}</p>
      <div v-else-if="state.phase === 'running'" class="empty"><span>◌</span><p>正在检测，完成后会自动生成总体总结。</p></div>
      <p v-else class="summary-overview">当前报告未提供总结。</p>
    </div>
  </section>
  <section v-if="state.report" id="shot-report" class="panel shot-panel">
    <div class="panel-title"><h2>逐镜头诊断</h2><a id="download" class="download" :href="`/artifacts/${state.run}/report.json`" download="frameproof-report.json">导出 JSON ↗</a></div>
    <div id="report-content">
      <div class="verdict" :class="{ clear: isClear, review: !isClear && state.report.status !== 'fail' }"><b>{{ summary?.verdict_label || fallbackLabel }}</b><small>{{ confirmedCount }} 项确定 / {{ state.report.findings.length - confirmedCount }} 项疑似</small></div>
      <article v-for="(finding, index) in state.report.findings" :key="`${finding.shot_id}-${finding.defect_type}-${index}`" class="finding">
        <div class="finding-top"><b>{{ defectLabels[finding.defect_type] || finding.defect_type }}</b><span class="zone">{{ finding.zone === 'confirmed' ? '确定' : '疑似' }} · {{ Math.round(finding.confidence * 100) }}%</span><button class="jump" :data-second="finding.timestamp" @click="emit('jump', finding.timestamp)">{{ finding.shot_id }} ↗</button></div>
        <p>{{ finding.evidence }}</p><p>证据来源：{{ finding.source }}</p>
      </article>
      <p v-if="!state.report.findings.length" class="memory-caption">{{ summary?.tasks_finished ? '已完成本次计划检查，检查范围内未检出缺陷。' : '已采样画面未检出缺陷；尚未完成的范围见下方详情。' }}</p>
      <div class="coverage"><b>检查覆盖与边界</b><p v-for="(item, index) in state.report.coverage" :key="index">{{ item.task }} / {{ item.status }}<br>{{ item.detail }}</p><p>模型置信度并非准确率；合成样例结果不能代表生产效果。</p></div>
    </div>
    <div id="feedback-area" class="feedback"><label for="feedback">复核反馈（可选）</label><form @submit.prevent="saveFeedback"><input id="feedback" v-model="state.feedback" placeholder="记录误报、漏报或复核意见" maxlength="1000" required><button id="feedback-btn" class="secondary" type="submit">保存反馈</button></form><span id="feedback-status" role="status">{{ state.feedbackStatus }}</span></div>
  </section>
</template>
