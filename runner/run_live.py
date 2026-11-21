"""Live joint run: let runner/run_case.py drive real UFO, then convert + check.

Requires the baseline environment (Python 3.12, UFO installed, model.local.json with a key).
This wrapper does not modify UFO internals.

Usage:
    python runner/run_live.py --out runs/live_web_success
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

RUNNER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(RUNNER_DIR.parent))

from trajectory.convert_ufo import convert  # noqa: E402
from checker.web_submit import check  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner-dir", type=Path, default=RUNNER_DIR, help="directory containing run_case.py")
    ap.add_argument("--case", choices=("web_success",), default="web_success")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    runner_dir = Path(args.runner_dir).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    cmd = [sys.executable, "-X", "utf8", "run_case.py", args.case, "--timeout", str(args.timeout)]
    print("$", " ".join(cmd), "(cwd=%s)" % runner_dir)
    try:
        proc = subprocess.run(cmd, cwd=runner_dir, text=True, encoding="utf-8",
                              errors="replace", capture_output=True)
    except OSError as exc:
        (out / "runner.stderr.log").write_text(str(exc), encoding="utf-8")
        print(exc, file=sys.stderr)
        return 2
    (out / "runner.stdout.log").write_text(proc.stdout, encoding="utf-8")
    (out / "runner.stderr.log").write_text(proc.stderr, encoding="utf-8")
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)

    m = re.search(r"^Run artifacts:[ \t]*(.+)$", proc.stdout, re.MULTILINE)
    if not m:
        print("cannot locate run directory from runner output", file=sys.stderr)
        return proc.returncode or 2
    run_dir = (runner_dir / m.group(1).strip()).resolve()
    print("run dir:", run_dir)

    raw_dir = out / "raw"
    shutil.copytree(run_dir, raw_dir)
    run_dir = raw_dir
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    check_result = check(manifest["run_id"], run_dir)
    check_passed = check_result["status"] == "completed"
    (out / "check.json").write_text(json.dumps(check_result, ensure_ascii=False, indent=2), encoding="utf-8")
    trajectory = convert(run_dir, out)
    ufo_success = trajectory["outcome"]["task_success"]
    summary = {
        "task_id": trajectory["task_id"],
        "mode": "live",
        "expected": trajectory["expected"],
        "ufo_status": trajectory["outcome"]["status"],
        "ufo_task_success": ufo_success,
        "check_status": check_result["status"],
        "check_passed": check_passed,
        "consistent": None if ufo_success is None else check_passed == ufo_success,
        "steps": trajectory["stats"]["steps"],
        "screenshots": trajectory["stats"]["screenshots"],
        "runner_exit_code": proc.returncode,
        "artifacts": {"trajectory": str(out / "trajectory.json"), "check": str(out / "check.json")},
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return proc.returncode or int(not (
        check_passed and ufo_success is True
        and trajectory["stats"]["steps"] and not trajectory["stats"]["missing_screenshots"]
    ))


if __name__ == "__main__":
    raise SystemExit(main())
