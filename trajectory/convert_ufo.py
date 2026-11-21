"""Convert UFO raw execution logs into the unified trajectory format.

Input  (a UFO run directory):
    manifest.json, result.json, response.log, screenshots/

Output (out_dir):
    trajectory.json, steps.csv, screenshots/step_XXXX_pre.png|post.png
"""
import argparse
import csv
import json
import shutil
from pathlib import Path


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _action_success(step):
    items = step.get("action_success") or []
    if not items:
        return None
    result = items[0].get("result") or {}
    return result.get("status")


def convert(run_dir, out_dir):
    run_dir, out_dir = Path(run_dir), Path(out_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8-sig"))
    live_trace = run_dir / "trajectory"
    log_dir = live_trace if live_trace.is_dir() else run_dir
    screenshot_dir = live_trace if live_trace.is_dir() else run_dir / "screenshots"
    rows = [r for r in read_jsonl(log_dir / "response.log") if r.get("clean_screenshot_path")]

    shots_dir = out_dir / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    steps, missing = [], []
    for i, row in enumerate(rows):
        pre_src = screenshot_dir / Path(row["clean_screenshot_path"]).name
        if i + 1 < len(rows):
            post_src = screenshot_dir / Path(rows[i + 1]["clean_screenshot_path"]).name
        else:
            post_src = screenshot_dir / "action_step_final.png"
            if not post_src.exists():
                post_src = pre_src

        pre_name = f"step_{i + 1:04d}_pre.png"
        post_name = f"step_{i + 1:04d}_post.png"
        for src, name in ((pre_src, pre_name), (post_src, post_name)):
            if src.exists():
                shutil.copy2(src, shots_dir / name)
            else:
                missing.append(str(src))

        actions = row.get("action") or []
        steps.append({
            "step_id": i + 1,
            "agent": row.get("agent_type"),
            "agent_status": row.get("status"),
            "application": row.get("app_root"),
            "window": row.get("application_process_name"),
            "action": {
                "functions": [a.get("function") for a in actions],
                "calls": row.get("function_call") or [],
                "arguments": [a.get("arguments") for a in actions],
                "targets": [a.get("target") for a in actions],
            },
            "action_status": _action_success(row),
            "result_text": row.get("result"),
            "pre_img": f"screenshots/{pre_name}",
            "post_img": f"screenshots/{post_name}",
            "raw_status": row.get("status"),
        })

    with open(out_dir / "steps.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["step_id", "agent", "status", "functions", "action_status", "pre_img", "post_img", "result_text"])
        for s in steps:
            w.writerow([s["step_id"], s["agent"], s["agent_status"],
                        ";".join(x for x in s["action"]["functions"] if x),
                        s["action_status"], s["pre_img"], s["post_img"],
                        (s["result_text"] or "")[:200]])

    success = result.get("task_success")
    trajectory = {
        "schema_version": "1.0",
        "task_id": manifest.get("run_id"),
        "source": "ufo",
        "case": manifest.get("case"),
        "app": (rows[0].get("app_root") if rows else None) or "msedge.exe",
        "request": manifest.get("request"),
        "expected": manifest.get("expected"),
        "created_at": manifest.get("created_at"),
        "status": "success" if success else ("failed" if success is False else "unknown"),
        "steps": steps,
        "outcome": {
            "task_success": success,
            "status": result.get("status"),
            "exit_code": result.get("exit_code"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "evidence": result.get("evidence"),
        },
        "stats": {
            "steps": len(steps),
            "screenshots": len(list(shots_dir.glob("*.png"))),
            "missing_screenshots": missing,
        },
    }
    (out_dir / "trajectory.json").write_text(
        json.dumps(trajectory, ensure_ascii=False, indent=2), encoding="utf-8")
    return trajectory


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    traj = convert(args.run_dir, out)
    print(json.dumps({"task_id": traj["task_id"], "status": traj["status"],
                      "steps": traj["stats"]["steps"],
                      "screenshots": traj["stats"]["screenshots"],
                      "missing": traj["stats"]["missing_screenshots"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
