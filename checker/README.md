# Checker 接口

这里放独立结果检查器。检查器必须以任务编号为主键，读取后端事件或目标文件，而不是只依赖 UFO 最后一张截图。

建议接口：`check(task_id, evidence_root) -> {status, evidence, checked_at}`。
