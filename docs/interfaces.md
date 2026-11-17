# 模块调用方式

1. `runner` 创建任务编号并启动 UFO。
2. UFO 输出原始轨迹和截图。
3. `trajectory` 将原始记录转换为统一格式。
4. `checker` 独立检查网页后端事件或文件内容。
5. runner 汇总 `task_status`、`actual_result` 和证据路径。
