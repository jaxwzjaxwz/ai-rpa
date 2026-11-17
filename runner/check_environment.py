"""Import-check UFO without model calls or desktop actions; report selected config only."""
import importlib
import json
import os
import platform
import sys
from pathlib import Path
from configure import ROOT, REPO

os.chdir(REPO)
sys.path.insert(0, str(REPO))
os.environ.update(UFO_API_KEY="not-a-real-key-import-check-only",
                  UFO_API_BASE="https://open.bigmodel.cn/api/paas/v4/chat/completions",
                  UFO_MODEL="glm-4.6v-flash")
report = {"kind": "environment_check_not_ufo_execution", "python": sys.version,
          "platform": platform.platform(), "imports": []}
for module in ("pywinauto", "uiautomation", "torch", "ufo.module.session_pool"):
    try:
        importlib.import_module(module)
        report["imports"].append({"module": module, "ok": True})
    except Exception as exc:
        report["imports"].append({"module": module, "ok": False, "error": str(exc), "type": type(exc).__name__})
report["passed"] = all(item["ok"] for item in report["imports"])
(ROOT / "logs/environment_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
