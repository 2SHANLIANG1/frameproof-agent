<script setup>
import { onMounted, provide, ref } from 'vue'
import { inspectionKey, useInspection } from './composables/useInspection.js'
import UploadPanel from './components/UploadPanel.vue'
import VideoWorkspace from './components/VideoWorkspace.vue'
import InspectionReport from './components/InspectionReport.vue'
import TechnicalDetails from './components/TechnicalDetails.vue'

const inspection = useInspection()
provide(inspectionKey, inspection)
const { state, reportVisible, reportHref, openTechnical } = inspection
const workspace = ref(null)
onMounted(inspection.initialize)
</script>

<template>
  <div class="app-shell" :class="{'has-report': reportVisible, 'work-started': state.workspaceOpen, 'show-technical': state.showTechnical}">
    <header class="topbar">
      <a class="brand" href="/" aria-label="FrameProof 首页"><svg viewBox="0 0 30 30" aria-hidden="true"><path fill="#1677ff" d="M3 4 15 13 27 4v22H3z"/><path fill="#55c6ff" d="M3 4v22l12-13z"/><path fill="#fff" d="m12 15 9-7v13h-9z"/></svg><b>FrameProof</b></a>
      <span class="brand-divider"/><span class="product-name">媒体质检工具</span>
      <nav><a href="#inputs">上传视频</a><a :href="reportHref" @click="!state.lastRun && inspection.openWorkspace()">检测报告</a><a href="#technical" @click.prevent="openTechnical">技术详情</a><span class="local-badge"><i/>本地运行</span></nav>
    </header>
    <main>
      <UploadPanel />
      <VideoWorkspace ref="workspace" />
      <InspectionReport @jump="workspace?.jumpTo($event)" />
      <TechnicalDetails />
      <footer><span>FrameProof · 视频质检项目</span><span>本地推理 · 证据可追溯 <span class="footer-separator">|</span> 合成样例仅用于功能演示</span></footer>
    </main>
    <div v-if="state.toast" id="toast" role="alert" class="toast">{{ state.toast }}</div>
  </div>
</template>
