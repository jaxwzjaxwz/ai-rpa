# UFO 网页与文件结果检查适配器

独立、只读，兼容 Python 3.12。保留原有 `checkers/` 演示程序；本目录可整体交给共用仓库的 `checker/`。支持网页、TXT、Word（DOCX/DOC）和 PDF 文件任务，不修改 runner。网页/TXT 仅使用标准库，DOCX/PDF 需 `python -m pip install -r checker/requirements.txt`（本项目根依赖也已包含）。

## Word（DOCX/DOC）和 PDF

仍调用 `check(task_id, evidence_root)`；file_success/file_failure 根据 destination 后缀选择 TXT/DOCX/DOC/PDF 检查。无需固定文件路径或固定报告正文。Word 支持 .docx 和旧 .doc。DOC 需额外安装 antiword 并加入 PATH，使用 UTF-8 文本提取和归一化空白后的包含匹配；缺少工具或无可提取文本返回 inconclusive，解析失败返回 not_completed。不调用 Word，也不转换或修改源文件。

```json
{
  "run_id": "document_run_001",
  "case": "file_success",
  "destination": "outputs/report.pdf",
  "expected_content": ["GUI Agent Automation Report", "Introduction"],
  "expected_pages": 1
}
```

DOCX 将 destination 改成 outputs/report.docx，并删除 expected_pages。expected_content 必须是非空字符串列表；不自动使用 TXT 的 token 或原演示的固定正文。DOCX 沿用原检查器的正文段落精确匹配规则，不检查表格、页眉、页脚。PDF 按提取文本进行包含匹配并归一化空白；expected_pages 可省略，省略时不限制页数。PDF 不执行 OCR，加密或无可提取文本返回 inconclusive。以上检查不证明排版、图片、来源文档或 GUI 操作过程正确。

文件缺失、空文件、损坏、缺少预期内容、PDF 页数不符返回 not_completed；输入或依赖问题返回 error。返回证据包含 SHA-256、大小、实际格式、缺失内容、DOCX 正文段落数或 PDF 页数。请使用每次独立目录和本次预期内容，避免把旧文件当作本次成果。文件权限等外层读取异常返回 error。

## TXT 文件任务

仍使用 `from checker import check` 和 `check(task_id, evidence_root)`。入口根据 manifest 的 case 自动选择检查器。TXT 配置示例：

```json
{
  "run_id": "file_run_001",
  "case": "file_success",
  "destination": "outputs/result.txt",
  "token": "UFO-file_run_001",
  "expected": "success"
}
```

case 支持 runner 已有的 file_success/file_failure。destination 可以是绝对路径，或相对于 evidence_root 的路径，不相对于启动 Python 的目录。搬迁旧证据时需显式更新旧绝对路径；检查器不会猜测或搜索替代文件。

按 token 比较文本，仅忽略文件末尾的回车和换行，不忽略空格。支持 UTF-8（含 BOM）、带 BOM 的 UTF-16、GB18030。无 BOM 时优先 UTF-8，不支持自动猜测无 BOM 的 UTF-16。返回证据包含实际路径、存在情况、字节数、SHA-256、解码编码及内容匹配结果。

文件不存在、不是普通文件或内容不符返回 not_completed；无法按支持的编码解码返回 inconclusive；配置不符、读取权限等异常返回 error。文件缺失不证明 UFO 尝试过保存或识别错误。expected=failure 不会反转实际结论。应使用每次独立目录和唯一 token，已有文件不能独立证明本次 GUI 操作发生过。

TXT 规则与网页不同：文件任务明确指定目标路径，缺失目标证明该保存目标未达成；网页缺失事件则不足以确定后端结果。直接调用 txt_file.check 时仍只接受 .txt；统一入口自动分发 DOCX/PDF。

## 调用

从包含 `checker/` 的项目根目录运行 Python：

```python
from checker import check

result = check("20261113_215341_131065_web_success", "本次运行目录")
print(result)
```

`task_id` 必须等于 `manifest.json` 的 `run_id`，不是 `case`，也不是 UFO 的 `baseline_...` 名称。`evidence_root` 直接指向本次运行目录，不是所有运行的父目录。

## 网页输入文件

- `manifest.json`：必需，包含 `run_id`、`case`、`route`、`name`、`message`。case 支持既有的 `web_success`、`web_failure`、`web_false_success`。
- `server_events.jsonl`：每行一个事件对象；按 `event=submission`、route 和完整 fields 精确匹配。
- `accepted_submissions.jsonl`：每行一个保存的字段对象，按完整 name/message 字典匹配。服务器仅在接受提交时创建它，缺失不一律视为错误。

配置缺失、格式损坏或编号不符返回 error。缺少事件或没有匹配事件返回 inconclusive。请在本次运行结束、证据写入完成后调用；检查器不会等待或重试，也不查询网络。

## 返回

返回普通字典，包含 `status`、`evidence`、`checked_at`。时间是检查结束时的 UTC ISO 8601 时间，非提交时间。

| status | 意义 |
| --- | --- |
| completed | 存在匹配的 accepted=true、HTTP 200 事件，且保存记录匹配 |
| not_completed | 匹配事件均未接受，且没有匹配保存记录 |
| inconclusive | 缺证据或事件与保存记录不能相互印证 |
| error | 检查输入或读取异常，不能作为任务失败结论 |

evidence 包含任务编号、预期字段、原因、文件存在情况，以及匹配事件和保存记录的文件相对路径、1 起始行号、原始记录。相对路径均相对于 evidence_root。多次提交会全部列出；目前不要求恰好提交一次。

旧事件没有 persisted/ui_claims_saved 字段仍可检查。页面成功、HTTP 200 或 persisted=true 均不单独作为完成证据。expected=failure 不会将实际未完成转换为 completed；是否符合场景预期、UFO 超时及错误识别由调用方处理。

这些状态名称是本适配器提出的约定，接入前需与 runner 维护者统一。该接口验证当前本地测试后端的保存文件，不代表生产数据库或端到端来源认证。未修改 UFO、runner 或远程仓库。

## 本地验证

```powershell
python -m unittest discover -s tests -p "test_*adapter.py" -v
```

测试使用临时目录构造现有证据格式，不启动 GUI、服务器或 UFO，不新增 GUI 测试场景。

### antiword 启动配置

优先使用环境变量 `ANTIWORD_EXE` 指定可执行文件完整路径，否则从 PATH 查找。Windows 请保留完整工具目录结构：`bin/antiword.exe` 与 `share/antiword/UTF-8.txt`。检查器自动以可执行文件所在目录启动子进程，DOC 使用绝对路径；不会改变调用程序的工作目录。可用 `ANTIWORDHOME` 指定字符映射目录，必须包含 UTF-8.txt；部分旧 Windows 版本忽略此变量，因此优先使用上述标准目录结构。

```powershell
$env:ANTIWORD_EXE = 'C:\tools\antiword\bin\antiword.exe'
```

缺少工具、映射文件或启动失败、超时、映射配置错误返回 inconclusive。工具报告文档解析失败返回 not_completed；证据保留退出码和最多 4000 字符的标准错误，方便定位原因。此配置不影响 DOCX/PDF。
