# Vue 3 前端开发

前端使用 Vue 3.5、Composition API、单文件组件和 Vite 7，保留蓝白媒体工具界面。Python 继续处理视频、模型调用与报告生成。没有通过 CDN 加载框架，构建后无需联网加载 JavaScript 依赖。

## 目录

```text
frontend/
  src/App.vue                         页面入口与组件组装
  src/components/UploadPanel.vue       选择文件、拖放、提示词输入
  src/components/VideoWorkspace.vue    播放器、镜头时间轴、检测设置
  src/components/InspectionReport.vue  总结、诊断、下载、复核反馈
  src/components/TechnicalDetails.vue  轨迹、用量、实体与证据台账
  src/composables/useInspection.js     应用状态、API 编排、轮询与资源清理
  src/lib/api.js                      请求及可中止的轮询等待
  src/lib/report.js                   报告格式与输入校验
  src/style.css                       响应式样式
  tests/                              Node.js 内置测试运行器
  pnpm-lock.yaml                      锁定依赖
web/                                  Vite 生成文件，由 Python 同源提供
```

状态通过应用级 composable 和 provide/inject 在组件之间共享；该单页面项目没有额外引入路由器或全局状态库。表单使用 v-model，列表使用 v-for，报告通过模板插值渲染，不拼接 HTML，也不使用 v-html。组件销毁时中止请求和轮询，并回收总结下载的 Blob URL。

## 直接体验

仓库随附已经构建的 web/。双击根目录 start.bat，或者按 README 启动 Python，然后访问 http://127.0.0.1:8765/。这种方式只需要 Python，不需要在演示机器上安装 Node.js。

## 开发与热更新

开发环境使用 Node.js 24 LTS、pnpm 11.25.0；可以使用官方 Node.js 安装包，再通过 npm 安装指定版本的 pnpm。

先在项目根目录启动后端：

```powershell
.venv\Scripts\python.exe server.py
```

另开终端，在 frontend/ 中运行：

```powershell
pnpm install --frozen-lockfile
pnpm dev
```

访问 http://127.0.0.1:5173/。Vite 只监听本机，/api、/media、/artifacts 代理到本机 8765。开发代理转发写请求时设置后端认可的本机 Origin；Python 原来的跨站请求校验仍保留。不要通过修改 Python 的来源白名单来迁就开发端口。

## 测试与构建

在 frontend/ 中执行：

```powershell
pnpm test
pnpm build
```

构建仅重建项目 web/ 下的前端产物，不处理 data/ 中的视频和报告。修改 Vue 源码后，需要重新构建才能在 8765 页面看到更新；5173 开发页面支持热更新。

依赖策略只允许锁定的 esbuild 安装脚本。升级 esbuild 时应同步检查 pnpm-workspace.yaml 中的版本规则。GitHub Actions 会依次执行前端安装、测试、构建与 Python 回归测试。

## 发布到 GitHub

同时提交 frontend/ 源码、锁文件和 web/ 构建结果。不要提交 frontend/node_modules/、.env 或 data/。页面需要 Python 的动态接口与模型服务，单独发布静态文件不能提供视频质检功能。
