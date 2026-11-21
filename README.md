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
| `checker/`              | 网页提交和文件落盘检查器                    |
| `trajectory/`           | UFO 原始轨迹转换器和统一轨迹 schema               |
| `examples/web_success/` | 脱敏后的网页成功样例：结果 JSON、后端事件、控制台日志、响应日志和 21 张截图 |
| `docs/`                 | 环境、接口和交付说明                                 |
| `tests/`                | 共用仓库级测试预留位置                                |
| `config/`               | 本地配置模板；真实密钥只能放在未跟踪的 `model.local.json`     |

## 安装与运行

1. 使用 Python 3.12 创建虚拟环境。
2. 安装 `requirements-lock.txt` 与 `src/ufo/requirements.txt` 中的依赖。
3. 复制 `config/model.local.example.json` 为 `runner/model.local.json`，填入模型地址、模型名和 API Key。Git 会忽略该文件。
4. 按 `runner/run_case.py` 的说明启动本地测试夹具并执行任务。

## 网页提交联合运行

在仓库根目录使用已安装 UFO 依赖的 Python 执行，输出目录需为新目录。

```powershell
python runner/run_live.py --out runs/live_web_success
```

Runner 启动本地表单并交给 UFO。表单的 `Name` 填写 `UFO Tester`，`Message` 填写本次测试编号，例如 `UFO-20261121_230549_790894_web_success`。独立检查器用这两个值核对服务端事件和已保存的提交记录。

| 输出 | 内容 |
| --- | --- |
| `summary.json`、`check.json` | UFO 结果、后端核验结论及证据 |
| `trajectory.json`、`steps.csv` | 有截图的步骤、动作及控件目标 |
| `screenshots/` | 结构化步骤关联的截图 |
| `raw/trajectory/` | 原始请求和响应日志、截图、UI 控件树 |
| `raw/server_events.jsonl`、`raw/accepted_submissions.jsonl` | 服务端事件和持久化记录 |
| `runner.stdout.log`、`runner.stderr.log`、`raw/console.log` | 联合运行和 UFO 日志 |

运行 `20261121_230549_790894_web_success` 以 `FINISH` 结束。后端接受并保存 1 次匹配提交，返回 HTTP 200。原始归档含 6 条响应记录和 21 张截图，转换后得到 4 个带截图的步骤和 8 张前后截图。

# 最终目标

完成一套能够交付的 AI-RPA 系统。
