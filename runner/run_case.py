"""Run real UFO and retain its original trajectory plus independent outcome checks."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from configure import ROOT, REPO, model_environment, write_config
from fixture_server import make_server

CASES = ("web_success", "web_failure", "file_success", "file_failure", "web_false_success")

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def prepare(case):
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + case
    folder = ROOT / "runs" / run_id
    folder.mkdir(parents=True)
    token = "UFO-" + run_id
    if case == "web_false_success":
        token = "TASK-" + uuid.uuid4().hex[:12]
    output = folder / "outputs"
    output.mkdir()
    failure = case.endswith("failure") or case == "web_false_success"
    manifest = dict(case=case, run_id=run_id, token=token, expected="failure" if failure else "success",
                    created_at=datetime.now().astimezone().isoformat())
    boundary = " Work only in the test application. Do not use terminals, scripts, or other applications."
    if case.startswith("web"):
        route = "/submit" if case == "web_false_success" else ("/failure" if failure else "/success")
        manifest.update(route=route, name="UFO Tester", message=token)
        request = (f"In the browser page titled UFO Baseline Form, enter Name 'UFO Tester' and Message '{token}', "
                   "then click Submit. Check the resulting page and report whether the submission actually succeeded. "
                   "If the page reports an error, stop and report failure; do not retry or alter the URL.")
    else:
        draft = folder / ("draft_" + run_id.split("_")[2] + ".txt")
        draft.write_text("", encoding="utf-8")
        manifest["draft"] = str(draft)
        if failure:
            # A normal file occupies the parent path. No ACL or system setting changes.
            blocker = output / "blocked_parent"
            blocker.write_text("UFO failure fixture: this is a file, not a directory.", encoding="utf-8")
            destination = blocker / "result.txt"
        else:
            destination = output / "result.txt"
        manifest["destination"] = str(destination)
        filename = r"blocked_parent\result.txt" if failure else "result.txt"
        request = (f"In the Notepad window titled '{draft.name}', replace its empty contents with exactly '{token}'. "
                   "Use Ctrl+Shift+S to open Save As. The draft is located in this trial's folder, which contains an outputs folder. "
                   "In the Save As dialog, open that outputs folder by double-clicking its folder item. "
                   f"Then replace the File name field with '{filename}' and click Save. "
                   "If the filename contains a backslash, enter exactly ONE separator, not two; JSON escaping must not produce doubled actual characters. "
                   "Avoid navigating the File menu. "
                   "Verify whether saving succeeded. If Windows reports an error, stop and "
                   "report failure. Do not change the destination, create directories, remove files, or use another application.")
        if failure:
            manifest["protocol_version"] = "file_failure_v2"
            request += (" Keep editing, Save As, and outcome inspection as ONE AppAgent subtask anchored to the main Notepad window; "
                        "do not reassign a standalone Save As dialog as a separate application. "
                        "Click Save at most ONCE. After that wait briefly and inspect both the main window and any modal error dialog. "
                        "Do not dismiss an error before recording its exact visible message and requesting a screenshot. "
                        "If Save As remains open without an explicit error, report save not completed and cause unconfirmed; never retry Save. "
                        "A single backslash is valid as a Windows path separator: do not diagnose it as an invalid filename character. "
                        "Only attribute a failure cause to visible evidence; distinguish observations from guesses. "
                        "Finish with a summary and FAIL status if saving was not completed, with no further UI action.")
    manifest["request"] = request + boundary
    dump(folder / "manifest.json", manifest)
    (folder / "request.txt").write_text(manifest["request"], encoding="utf-8")
    dump(folder / "result.json", {"status": "prepared_not_executed", "task_success": None})
    return folder, manifest

def verify(folder, manifest, exit_code, timed_out):
    evidence = {}
    if manifest["case"].startswith("web"):
        events = read_jsonl(folder / "server_events.jsonl")
        submissions = [e for e in events if e["event"] == "submission"]
        matching = [e for e in submissions if e["fields"] ==
                    {"name": manifest["name"], "message": manifest["message"]}]
        success = any(e["accepted"] for e in matching)
        failure_observed = any(e["http_status"] == 503 for e in matching)
        evidence.update(submissions=submissions, injected_failure_observed=failure_observed)
    else:
        path = Path(manifest["destination"])
        exists = path.is_file()
        content = None
        if exists:
            data = path.read_bytes()
            for encoding in ("utf-8-sig", "utf-16", "gb18030"):
                try:
                    content = data.decode(encoding).rstrip("\r\n")
                    break
                except UnicodeError:
                    pass
            evidence["sha256"] = hashlib.sha256(data).hexdigest()
        success = exists and content == manifest["token"]
        failure_observed = False  # Absence alone never proves an attempted save or error recognition.
        evidence.update(file_exists=exists, content_matches=success,
                        injected_failure_observed="requires_trajectory_review" if manifest["expected"] == "failure" else None)
    status = "task_succeeded" if success else "task_not_completed"
    if timed_out:
        status = "timeout"
    elif exit_code != 0:
        status = "execution_error"
    elif failure_observed:
        status = "injected_failure_observed"
    console_path = folder / "console.log"
    console = console_path.read_text(encoding="utf-8", errors="replace") if console_path.exists() else ""
    codes = set(re.findall(r'''['"]code['"]\s*:\s*['"](\d+)['"]''', console))
    if not success and ("1305" in codes or "1302" in codes):
        status = "api_unavailable"
        evidence["api_error"] = "1305_service_overloaded" if "1305" in codes else "1302_rate_limited"
    elif not success and "1113" in codes:
        status = "api_account_blocked"
        evidence["api_error"] = "1113_account_balance"
    elif not success and "chat/completions/chat/completions" in console:
        status = "configuration_error"
        evidence["api_error"] = "duplicated_chat_completions_path"
    elif not success and ("Extra data:" in console or "Invalid JSON:" in console):
        status = "model_output_parse_error"
    elif not success and "API request timed out" in console:
        status = "api_timeout"
    trajectory = folder / "trajectory"
    steps = read_jsonl(trajectory / "response.log")
    evidence["logged_steps"] = len(steps)
    evidence["api_error_codes_seen"] = sorted(codes)
    evidence["agent_terminal_status"] = steps[-1].get("status") if steps else None
    if not success and steps and not steps[-1].get("status"):
        status = "model_state_error"
    evidence["screenshots"] = len(list(trajectory.glob("*.png")))
    return dict(status=status, task_success=success, exit_code=exit_code, timed_out=timed_out,
                expected=manifest["expected"], evidence=evidence,
                agent_failure_recognition="requires_trajectory_review" if manifest["expected"] == "failure" else None)

def run(folder, manifest, timeout):
    write_config()
    try:
        env, public = model_environment()
    except ValueError as exc:
        dump(folder / "result.json", dict(status="blocked_missing_api_key", task_success=None, reason=str(exc)))
        print(str(exc))
        return 2
    dump(folder / "model.json", public)
    # Preserve the exact harness used, including prompt changes between trials.
    source_dir = folder / "source"
    source_dir.mkdir(exist_ok=True)
    for name in ("run_case.py", "configure.py", "fixture_server.py"):
        shutil.copy2(ROOT / name, source_dir / name)
    env["UFO_TRACE_DIR"] = str(folder)
    env["UFO_COMPAT_ADAPTER"] = "1"
    for name in ("agents.yaml", "zz_baseline.yaml"):
        shutil.copy2(REPO / "config/ufo" / name, folder / name)
    patch = ROOT / "ufo-compatibility.patch"
    if patch.exists():
        shutil.copy2(patch, folder / patch.name)
    server = None
    if manifest["case"].startswith("web"):
        server = make_server(folder, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}{manifest['route']}"
        browsers = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
                    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")]
        browser = next((p for p in browsers if p.exists()), None)
        if not browser:
            server.shutdown()
            raise RuntimeError("Edge or Chrome is required")
        subprocess.Popen([str(browser), "--new-window", "--start-maximized", url])
        manifest["url"] = url
        manifest["request"] = f"Use the test page at {url}. " + manifest["request"]
        (folder / "request.txt").write_text(manifest["request"], encoding="utf-8")
        dump(folder / "manifest.json", manifest)
    else:
        subprocess.Popen(["notepad.exe", manifest["draft"]])
    task = "baseline_" + manifest["run_id"]
    command = [sys.executable, "-m", "ufo", "--task", task, "--request", manifest["request"]]
    dump(folder / "command.json", {"argv": command, "cwd": str(REPO)})
    dump(folder / "result.json", {"status": "running", "task_success": None})
    started = time.monotonic()
    timed_out = False
    try:
        with (folder / "console.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.terminate()
                process.wait(timeout=20)
        trajectory = REPO / "logs" / task
        if trajectory.exists():
            shutil.copytree(trajectory, folder / "trajectory")
            steps = read_jsonl(folder / "trajectory/response.log")
            candidates = []
            for step in reversed(steps):
                screenshot = step.get("clean_screenshot_path")
                if screenshot:
                    local = folder / "trajectory" / Path(screenshot).name
                    if local.exists():
                        candidates.append(str(local))
            dump(folder / "screenshot_review_candidates.json", {
                "note": "Review these action-linked screenshots visually; final automatic capture is not sufficient evidence by itself.",
                "latest_action_screenshots": candidates[:5]})
        result = verify(folder, manifest, process.returncode, timed_out)
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        dump(folder / "result.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        if server:
            server.shutdown()
            server.server_close()
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=CASES)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    folder, manifest = prepare(args.case)
    print(f"Run artifacts: {folder}", flush=True)
    if not args.prepare_only:
        raise SystemExit(run(folder, manifest, args.timeout))
