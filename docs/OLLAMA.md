# 本地 Ollama / 千问视觉模型

支持 **Ollama 原生 `/api/chat`**，视频抽样帧直接发往本机服务，无需 API Key。外部 HTTPS 模型适配器仍可选用。

## 安装与配置

从 [Ollama 官网](https://ollama.com/download)安装并运行 Ollama，再在项目目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-ollama.ps1
```

脚本下载 `qwen3-vl:8b-instruct`，检查 vision 能力，并保存本地 `.env`。重复运行可以续传。模型由 Ollama 管理，不放在 GitHub 源码包里；约 6.1GB 的下载大小以[官方模型页](https://ollama.com/library/qwen3-vl:8b-instruct)为准。程序不改变 Ollama 的模型存储位置。

已有其他千问视觉模型时也可指定：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-ollama.ps1 -Model qwen3.5:9b
```

本次用户机器有 V100 16GB 显存。默认选用 8B 量化视觉模型、16384 token 上下文，不把 30B/32B 作为该机器的默认配置。其他硬件的速度和显存占用需要实际验证。

Qwen3-VL 是这里用于替代云端视觉取证调用的本地开源模型，不等同于参考材料中的云端 Plus / Flash 型号；不能照搬其能力或评测数值。

## 使用

1. 重启 FrameProof：双击 `start.bat`。
2. 打开 `http://127.0.0.1:8765`。
3. 页面检测模型已安装后，默认选择“本机 Ollama”，每个子问题预算默认 3 步。
4. 上传视频或运行内置样例，等待真实模型推理和取证。首次加载模型、视觉网格推理可能较慢。
5. 报告 `provider=ollama`，`model` 是实际调用名称，usage 记录实际 Token。

界面仍可切回“离线演示”快速验证工具链。本地真实模式会有实际 Token 统计，不产生云端 API 费用。

## 复现真实模型调用

```powershell
.venv\Scripts\python scripts/ollama_smoke.py
.venv\Scripts\python scripts/ollama_smoke.py --full --budget 3
```

第一条对比两个真实解码帧，第二条运行完整控制循环。记录保存在 `data/ollama-validation/`；这些是运行记录，并非单元测试。模型判断可能错误，结果不保证每次完全相同。

## 本地配置

```dotenv
QC_PROVIDER=ollama
QC_OLLAMA_BASE=http://127.0.0.1:11434
QC_MODEL=qwen3-vl:8b-instruct
QC_ENHANCED_MODEL=
QC_ENABLE_LIVE=1
QC_TIMEOUT_SEC=300
QC_OLLAMA_NUM_CTX=16384
```

增强模型留空表示同模型换采样复核。请求默认关闭 thinking、使用零温度和 JSON Schema，镜头编号约束为输入原始 ID。每次最多生成 1800 token，上下文默认 16384。模型默认保留 10 分钟，实际释放时间由 Ollama 管理。

只接受 `127.0.0.1` / `localhost` / `::1` 回环服务地址，本地调用绕过系统 HTTP 代理。外部模型仍要求 HTTPS。只能读文本的 Qwen 模型不能作为视觉探针。

## 排查

请使用完整标签 `qwen3-vl:8b-instruct`。默认 `qwen3-vl:8b` 是思考版，本机实测即使传入 `think=false`，检查项编译仍可能耗尽 1800 token 预算而没有最终 JSON。JSON Schema 不能替代正确的模型选型。本项目因此在就绪检测和配置脚本中提示使用指令版，不读取思考内容来拼造答案。参见 [Ollama 维护者说明](https://github.com/ollama/ollama/issues/16945)。

- 尚未安装：运行 `ollama list`，核对名称和 `.env` 完全一致，或重新运行下载脚本。
- 无法连接：确认 Ollama 正在运行，且本机 `11434` 端口可用。
- 显存不足：先检查 `ollama ps` 是否加载其他模型，自行停止不需要的模型，或把上下文降到 8192。
- 超时：检查是否使用 GPU，首次加载请留出时间。按实际情况调整 `QC_TIMEOUT_SEC`，上限 1800 秒。
- JSON / 镜头校验失败：界面明确报错，不会用离线结果替代模型结果。
- 当前仅有静音预检，未接 ASR；接入视觉模型不等于实现音画同步检测。

官方参考：[Chat API](https://docs.ollama.com/api/chat)、[结构化输出](https://docs.ollama.com/capabilities/structured-outputs)。
