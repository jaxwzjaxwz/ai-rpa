# 操作轨迹

| 步骤 | 代理 | 状态 | 操作 |
|---|---|---|---|
| 0 | HostAgent | ASSIGN | "select_application_window" |
| 1 | AppAgent | CONTINUE | ["set_edit_text(id='22', name='Name', text='UFO Tester', clear_current_text=True)"] |
| 2 | AppAgent | CONTINUE | ["set_edit_text(id='24', name='Message', text='UFO-20261113_215341_131065_web_success', clear_current_text=True)"] |
| 3 | AppAgent | CONTINUE | ["click_input(id='25', name='Submit', button='left', double=False)"] |
| 4 | AppAgent | FINISH | [] |
| 5 | HostAgent | FINISH | "no_action" |
