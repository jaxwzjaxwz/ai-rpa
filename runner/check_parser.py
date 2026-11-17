"""Conservative syntax adapter checks. No UI or model requests."""
import json
import os
import sys
from configure import ROOT, REPO
sys.path.insert(0, str(REPO))
from ufo.utils import json_parser

os.environ["UFO_COMPAT_ADAPTER"] = "1"
assert json_parser('{"status":"CONTINUE","action":{"function":"click_input"}}')["action"]["status"] == "CONTINUE"
assert json_parser('{"x":1}}') == {"x": 1}
for invalid in ('{"x":1}{"x":2}', '{"x":1} executable text', '{"x":1}}}'):
    try:
        json_parser(invalid)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError(invalid)
os.environ.pop("UFO_COMPAT_ADAPTER")
try:
    json_parser('{"x":1}}')
except json.JSONDecodeError:
    pass
else:
    raise AssertionError("Adapter must be opt-in")
report = dict(passed=True, checks=["explicit_status_mapping", "single_redundant_brace",
                                  "ambiguous_extra_content_rejected", "adapter_opt_in_only"])
(ROOT / "logs/parser_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
