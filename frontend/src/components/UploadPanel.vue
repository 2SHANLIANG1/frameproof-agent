<script setup>
import { ref } from 'vue'
import { useInspectionContext } from '../composables/useInspection.js'
const { state, disabled, uploadFile, chooseSample, updatePrompt, openWorkspace } = useInspectionContext()
const fileInput = ref(null)
const dragover = ref(false)
function onFileChange(event) {
  const file = event.target.files[0]
  event.target.value = ''
  uploadFile(file)
}
function onDrop(event) {
  dragover.value = false
  if (!disabled.value) uploadFile(event.dataTransfer.files[0])
}
</script>
<template>
<section class="hero" id="inputs"><div class="hero-title"><h1>上传视频，开始视频质检</h1><p>从画面一致性到提示词符合度，让每个问题都有迹可循</p></div>
<div class="upload-zone" id="upload-zone" :class="{dragover}" @dragenter.prevent="dragover = !disabled" @dragover.prevent="dragover = !disabled" @dragleave.prevent="dragover = false" @drop.prevent="onDrop"><svg class="folder-icon" viewBox="0 0 72 58" aria-hidden="true"><path d="M7 12a4 4 0 0 1 4-4h18l7 7h25a4 4 0 0 1 4 4v30H7z" fill="#d9e4f3"/><path d="M9 18h50a4 4 0 0 1 4 4v24H5V22a4 4 0 0 1 4-4" fill="#fff" stroke="#c4d3e9" stroke-width="2"/><path d="M3 26h60l-6 25H9z" fill="#e7eef8"/><circle cx="58" cy="42" r="12" fill="#1677ff"/><path d="M58 47V36m-4 4 4-4 4 4m-11 3v6h14v-6" fill="none" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg><p class="upload-callout">拖拽视频到这里，或 <button id="upload-btn" :disabled="disabled" @click="fileInput.click()" class="text-button">选择一个文件</button> 上传</p><input id="upload" ref="fileInput" :disabled="disabled" @change="onFileChange" type="file" accept="video/*,.mp4,.mov,.webm" hidden><p class="upload-formats">支持 MP4、MOV、WebM · 最大 60 MB · 最长 180 秒</p><p class="sample-hint">没有测试视频？试试我们的 <button id="sample-btn" :disabled="disabled" @click="chooseSample" class="text-button">示例视频</button></p></div>
<p id="upload-name" class="upload-status" role="status">{{ state.uploadStatus || '视频仅在本机处理，上传后可预览并设置检查要求' }}</p>
<div class="prompt-field"><div class="field-title"><label for="prompt-input">生成提示词 / 检查要求</label><span id="prompt-count">{{ state.prompt.length }} / 4000</span></div><textarea id="prompt-input" :value="state.prompt" :disabled="disabled" @input="updatePrompt($event.target.value)" rows="3" maxlength="4000" placeholder="输入生成视频时使用的提示词，或希望检查的内容，例如：主角全程穿米色外套，场景由天台切换到档案室。"></textarea><div class="prompt-bottom"><span>用文字描述要求，模型将据此逐项检查</span><button id="configure-btn" :disabled="disabled" @click="openWorkspace" class="continue-button">检测设置 <span>→</span></button></div></div>
<div class="benefits" id="benefits" v-if="!state.workspaceOpen"><div class="benefit-copy"><span class="section-caption">你将获得</span><article><span class="benefit-check">✓</span><div><h3>逐项核查视频内容</h3><p>结合生成提示词，检查人物外观、场景要素与可见画面缺陷。</p></div></article><article><span class="benefit-check">✓</span><div><h3>问题定位到具体镜头</h3><p>沿时间轴查看可疑画面，保留抽样证据与前后镜头对照。</p></div></article><article><span class="benefit-check">✓</span><div><h3>一份可追溯的检测报告</h3><p>区分确定缺陷、疑似问题与检查范围，支持文字及 JSON 导出。</p></div></article></div><div class="report-illustration" aria-hidden="true"><div class="mini-window"><div class="mini-title"><span class="mini-dot"></span> 视频检测报告 <span>报告示意</span></div><div class="mini-screen"><svg viewBox="0 0 290 110"><rect width="290" height="110" fill="#e9f1ff"/><path d="m0 110 74-74 54 44 52-61 110 91" fill="#c9dcfb"/><path d="m105 110 66-52 75 52" fill="#a7c7f8"/><circle cx="223" cy="26" r="12" fill="#fff"/></svg><span class="play-mark">▶</span></div><div class="mini-time"><span>00:00</span><span>00:15</span></div><div class="mini-timeline"><i></i><i></i><i></i><i></i><i></i><i></i></div><div class="mini-track"><svg viewBox="0 0 290 30"><path d="M0 17h15l3-5 4 10 3-7h18l4 4 4-10 4 8h20l3-6 4 12 4-7h26l3-4 5 8 4-5h24l4-9 5 16 4-7h20l5-4 5 8 4-5h28l4-6 5 12 4-5h26" fill="none" stroke="#75a5f1" stroke-width="1.5"/></svg></div></div><div class="mini-result"><div class="mini-result-title"><span>✓</span> 证据与结论</div><div class="skeleton wide"></div><div class="skeleton"></div><div class="mini-tag">镜头定位</div><div class="skeleton wide"></div><div class="skeleton short"></div><div class="mini-result-foot">可核查 · 可导出</div></div></div></div>
</section>
</template>
