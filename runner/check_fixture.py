"""Validate failure injection and oracle behavior without calling a model or controlling UI."""
import json
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from fixture_server import make_server
from run_case import verify
from configure import ROOT

def main():
    checks = []
    with tempfile.TemporaryDirectory(prefix="fixture_check_", dir=ROOT) as tmp:
        folder = Path(tmp)
        server = make_server(folder, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for route, expected_status in (("/success", 200), ("/failure", 503)):
                request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}{route}",
                    data=urllib.parse.urlencode({"name": "UFO Tester", "message": "fixture-check"}).encode())
                try:
                    response = urllib.request.urlopen(request)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    assert response.status == expected_status
                    body = response.read().decode()
                    assert ("Submission successful" if expected_status == 200 else "Submission failed") in body
                checks.append({"check": route, "http_status": expected_status, "passed": True})
            accepted = (folder / "accepted_submissions.jsonl").read_text().splitlines()
            assert len(accepted) == 1, "Failed submission must not be persisted"
            checks.append({"check": "failed_submission_not_saved", "passed": True})
            blocker = folder / "blocked_parent"
            blocker.write_text("fixture")
            target = blocker / "result.txt"
            try:
                target.write_text("should fail")
                raise AssertionError("Failure fixture unexpectedly writable")
            except OSError:
                checks.append({"check": "invalid_parent_rejects_save", "passed": True})
            result = verify(folder, {"case": "file_failure", "destination": str(target),
                                    "token": "test", "expected": "failure"}, 0, False)
            assert result["status"] == "task_not_completed"
            assert result["agent_failure_recognition"] == "requires_trajectory_review"
            checks.append({"check": "missing_file_does_not_prove_handled_failure", "passed": True})
        finally:
            server.shutdown()
            server.server_close()
    report = {"kind": "infrastructure_check_not_ufo_execution", "checks": checks}
    (ROOT / "logs/fixture_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
