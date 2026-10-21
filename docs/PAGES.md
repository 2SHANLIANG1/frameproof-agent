# 在线展示版

访问：**https://2shanliang1.github.io/frameproof-agent/**

这是面向项目审阅的独立 Vue 3 页面。访客无需安装依赖或连接本地模型，即可播放视频、切换案例、点击镜头定位、查看采样网格、实体档案、证据台账与检查覆盖，并下载 JSON 或文字总结。

## 数据来源

- 潜水视频：本机已完成的 Ollama / `qwen3-vl:8b-instruct` 运行，耗时约 213.5 秒、65 次模型调用；7 项任务完成计划抽样，未检出缺陷。仅覆盖采样画面。
- 外观漂移：程序生成的受控视频，经实际解码、外套色块测量与第二采样点对照，定位第 4 镜头的外观漂移。这不是通用模型检测，也不代表真实视频准确率。

公开资源位于 `showcase/public/demo/`，`manifest.json` 包含两个案例的元信息与结构化报告。仅发布精选示例，不自动打包 `data/`、用户上传、复核记录、密钥或模型权重。

在线页不上传视频、不发起模型请求、不保存反馈。它展示已完成的检测结果，不通过计时动画假装现场推理。需体验完整检测时，下载仓库，按 README 启动 Python 与 Ollama。

## 构建与发布

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend test
pnpm --dir frontend build:showcase
pnpm --dir frontend exec vite preview --mode showcase --host 127.0.0.1 --port 4173
```

本地预览：`http://127.0.0.1:4173/frameproof-agent/`。展示版产物输出到 `showcase-dist/`，使用 `/frameproof-agent/` 资源前缀，不覆盖本地完整程序的 `web/`。普通 `pnpm --dir frontend build` 仍生成 Python 服务使用的本地前端。

`.github/workflows/pages.yml` 在 main 更新后安装依赖、运行前端测试、构建并部署 GitHub Pages。仓库 Pages 的发布来源需设为 GitHub Actions。更新示例时，应同步元信息、实际报告、视频、预览图和报告引用的所有采样网格，并明确标记模型运行或合成测量的来源。
