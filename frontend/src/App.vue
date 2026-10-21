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
      <a class="brand" href="/" aria-label="视频质检工具首页"><b>视频质检工具</b></a>
      <nav><a href="#inputs">上传视频</a><a :href="reportHref" @click="!state.lastRun && inspection.openWorkspace()">检测报告</a><a href="#technical" @click.prevent="openTechnical">技术详情</a><span class="local-badge"><i/>本地运行</span></nav>
    </header>
    <main>
      <UploadPanel />
      <VideoWorkspace ref="workspace" />
      <InspectionReport @jump="workspace?.jumpTo($event)" />
      <TechnicalDetails />
      <footer><span>视频质检项目</span><span>本地推理 · 证据可追溯 <span class="footer-separator">|</span> 合成样例仅用于功能演示</span></footer>
    </main>
    <div v-if="state.toast" id="toast" role="alert" class="toast">{{ state.toast }}</div>
  </div>
</template>
