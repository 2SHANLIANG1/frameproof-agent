# 上传 GitHub

本机目录为 `D:\Projects\frameproof-agent`，主分支为 `main`。仓库首页提供演示短片、真实报告截图、组件说明与启动方式。

1. 在 GitHub 创建一个空仓库，例如 `frameproof-agent`。使用本项目 README 时，不要同时自动创建另一份 README。
2. 在项目目录打开终端。首次使用 Git 请先设置你自己的提交作者信息。
3. 依次运行以下命令，将示例地址替换为你自己的仓库：

```powershell
git status
git add .
git commit -m "Build FrameProof video QC agent demo"
git remote add origin https://github.com/YOUR_USERNAME/frameproof-agent.git
git push -u origin main
```

`.gitignore` 已排除虚拟环境、用户视频、运行报告、复核库和 `.env`。提交前可再次检查：

Vue 源码在 `frontend/`，请提交 `package.json`、pnpm 锁文件、Vue 组件与 `web/` 构建结果。`frontend/node_modules/` 已忽略。更改 Vue 源码后，在 `frontend/` 执行 `pnpm build` 更新演示页面；直接运行已构建版本无需 Node.js。开发方式见 [FRONTEND.md](FRONTEND.md)。

```powershell
git status --short
git check-ignore .env .venv data
```

不要手动强制添加这些文件。仓库中的 `docs/demo.png` 是程序生成素材的页面截图，可以随项目发布。第三方 PDF 没有加入源码包。

仓库首页包含项目介绍、截图、启动方式、实现边界和验证说明。可将项目置顶到个人主页，向 HR 提供仓库链接。完整交互需要运行 Python 后端，GitHub Pages 不能直接运行该后端。
