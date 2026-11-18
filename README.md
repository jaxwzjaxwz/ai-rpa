# AI-RPA 共用仓库

本仓库用于三人协作交付 AI-RPA 系统，当前基于 Microsoft UFO 完成了一次网页表单正常提交的端到端样例。仓库包含源码、运行脚本、接口说明和代表性运行证据。

## 当前验证结果

- 模型：阿里云百炼 `qwen3-vl-plus`。
- 运行编号：`20261113_215341_131065_web_success`。
- UFO 结果：`task_succeeded`，退出码 0，6 条操作记录，21 张截图，终端状态 `FINISH`。
- 独立结果检查：后端收到一次匹配字段的 POST，HTTP 200，`accepted=true`；提交记录保存在 `example/web_success_accepted_submissions.jsonl`。

## 目录说明

| 目录 | 用途 |
|---|---|
| **目录**                  | **用途**                                     |
| ----------------------- | ------------------------------------------ |
| `src/ufo/`              | Microsoft UFO 源码、配置示例、测试和资源                |
| `runner/`               | 统一运行入口、配置生成、网页测试工具和环境检查脚本                  |
| `checker/`              | 结果检查接口预留位置：网页提交和文件落盘检查器                    |
| `trajectory/`           | UFO 原始轨迹转换器及统一轨迹 schema 预留位置               |
| `examples/web_success/` | 脱敏后的网页成功样例：结果 JSON、后端事件、控制台日志、响应日志和 21 张截图 |
| `docs/`                 | 环境、接口和交付说明                                 |
| `tests/`                | 共用仓库级测试预留位置                                |
| `config/`               | 本地配置模板；真实密钥只能放在未跟踪的 `model.local.json`     |

## 安装与运行

1. 使用 Python 3.12 创建虚拟环境。
2. 安装 `requirements-lock.txt` 与 `src/ufo/requirements.txt` 中的依赖。
3. 复制 `config/model.local.example.json` 为本地 `model.local.json`，填入自己的 API Key；该文件被 `.gitignore` 排除。
4. 按 `runner/run_case.py` 的说明启动本地测试夹具并执行任务。

# 最终目标

完成一套能够交付的 AI-RPA 系统。
