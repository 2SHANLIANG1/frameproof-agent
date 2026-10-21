<script setup>
import { ref } from 'vue'
import { useInspectionContext } from '../composables/useInspection.js'
import { formatTime } from '../lib/report.js'

const { state, selected, shots, disabled, modeDescription, modelOption, selectVideo, runInspection } = useInspectionContext()
const player = ref(null)
function jumpTo(second) {
  if (!player.value) return
  player.value.currentTime = Number(second)
  player.value.pause()
  state.activeSecond = Number(second)
}
defineExpose({ jumpTo })
</script>

<template>
  <section v-if="state.workspaceOpen && selected" id="workspace" class="workspace">
    <div class="section-heading"><h2>视频与检测设置</h2><span>确认输入后开始质检</span></div>
    <div class="work-grid">
      <section class="panel video-panel">
        <div class="panel-title"><h2>视频预览</h2><span id="video-label" class="subtle">{{ selected.example ? '示例视频' : selected.synthetic ? '合成视频' : '上传视频' }} · {{ selected.duration_sec.toFixed(1) }}s</span></div>
        <div class="player-wrap">
          <video id="player" ref="player" :src="`/media/${encodeURIComponent(selected.video_id)}/video.mp4`" :poster="`/media/${encodeURIComponent(selected.video_id)}/poster.jpg`" controls preload="metadata" playsinline />
          <span class="video-tag">{{ selected.example ? 'LOCAL EXAMPLE VIDEO' : selected.synthetic ? 'SYNTHETIC TEST FOOTAGE' : 'LOCAL UPLOADED VIDEO' }}</span>
        </div>
        <div class="video-caption"><h3 id="video-title">{{ selected.title }}</h3><span id="asset-tag" class="asset-tag">{{ shots.length }} SHOTS / {{ selected.segmentation ? '等长分段' : '已知镜头表' }}</span></div>
        <div class="timeline-heading"><span>镜头时间轴</span><span>点击定位画面</span></div>
        <div id="timeline" class="timeline">
          <button v-for="(shot, index) in shots" :key="shot.shot_id" class="shot" :class="{ selected: state.activeSecond === shot.t_start, defect: state.report?.findings.some(f => f.shot_id === shot.shot_id) }"
            :title="`${shot.shot_id} · ${shot.t_start.toFixed(2)}s`" :data-second="shot.t_start" @click="jumpTo(shot.t_start)">{{ String(index + 1).padStart(2, '0') }}</button>
        </div>
        <div class="timeline-times"><span>00:00</span><span id="duration">{{ formatTime(selected.duration_sec) }}</span></div>
        <details class="prompt-box"><summary>当前检查要求</summary><p id="prompt-text">{{ state.prompt.trim() || '尚未填写提示词，可在顶部直接输入检查要求。' }}</p></details>
      </section>
      <section class="panel config-panel">
        <div class="panel-title"><h2>检测设置</h2></div>
        <label for="scenario">当前视频 / 切换样例</label>
        <select id="scenario" :value="state.selectedId" :disabled="disabled" @change="selectVideo($event.target.value)">
          <option v-for="video in state.videos" :key="video.video_id" :value="video.video_id">{{ video.original_filename || video.title }}</option>
        </select>
        <label for="mode">运行方式</label>
        <div class="mode-box"><select id="mode" v-model="state.mode" :disabled="disabled"><option value="offline">离线样例演示</option><option value="live">{{ modelOption }}</option></select><p id="mode-description">{{ modeDescription }}</p></div>
        <div class="budget-row"><label for="budget">每项检查步数</label><output id="budget-value">{{ state.budget }} 步</output></div>
        <input id="budget" v-model.number="state.budget" :disabled="disabled" type="range" min="1" max="8">
        <div class="check-list"><span>✓ 规则预检</span><span>✓ 视觉取证</span><span>✓ 独立采样复核</span></div>
        <details><summary>高级设置：自定义镜头表</summary><p class="help">上传视频默认等长分段，并非自动镜头检测；可替换真实镜头表。步数预算仅作用于模型调度。</p><textarea id="metadata" v-model="state.metadataText" :disabled="disabled" rows="6" spellcheck="false" aria-label="视频元信息 JSON" /></details>
        <button id="run-btn" class="primary" :disabled="disabled" @click="runInspection">{{ state.busy === 'inspection' ? '正在取证' : '开始质检' }} <span>{{ state.busy === 'inspection' ? '◌' : '→' }}</span></button>
        <div id="run-status" class="run-status" role="status">{{ state.runStatus }}</div>
      </section>
    </div>
  </section>
</template>
