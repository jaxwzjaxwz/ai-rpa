"""Check existing web evidence without executing UFO or contacting a server."""

import json
from datetime import datetime, timezone
from pathlib import Path


def _jsonl(path):
    if not path.exists():
        return None
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{number}: expected a JSON object")
            records.append((number, value))
    return records


def check(task_id, evidence_root):
    """Return {status, evidence, checked_at}; never write to the evidence directory.

    task_id is the manifest run_id. evidence_root is that run's directory.
    Only existing web cases are supported; execution health belongs to the runner.
    """
    evidence = {"task_id": task_id, "submission_events": [], "saved_records": []}

    def result(status, reason):
        evidence["reason"] = reason
        return {"status": status, "evidence": evidence,
                "checked_at": datetime.now(timezone.utc).isoformat()}

    try:
        if not isinstance(task_id, str) or not task_id:
            return result("error", "task_id must be a nonempty string")
        root = Path(evidence_root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
        if not isinstance(manifest, dict):
            return result("error", "manifest.json must contain an object")
        if manifest.get("run_id") != task_id:
            return result("error", "task_id does not match manifest.run_id")
        if manifest.get("case") not in {"web_success", "web_failure", "web_false_success"}:
            return result("error", "Unsupported case; this adapter checks web submissions only")
        for key in ("name", "message", "route"):
            if not isinstance(manifest.get(key), str) or not manifest[key]:
                return result("error", f"Missing or invalid manifest field: {key}")
        fields = {"name": manifest["name"], "message": manifest["message"]}
        evidence.update(manifest="manifest.json", route=manifest["route"], expected_fields=fields)
        events = _jsonl(root / "server_events.jsonl")
        saved = _jsonl(root / "accepted_submissions.jsonl")
        evidence["files_present"] = {"server_events.jsonl": events is not None,
                                     "accepted_submissions.jsonl": saved is not None}
        matching = [(line, item) for line, item in (events or [])
                    if item.get("event") == "submission"
                    and item.get("route") == manifest["route"] and item.get("fields") == fields]
        stored = [(line, item) for line, item in (saved or []) if item == fields]
        evidence["submission_events"] = [dict(path="server_events.jsonl", line=line, record=item)
                                          for line, item in matching]
        evidence["saved_records"] = [dict(path="accepted_submissions.jsonl", line=line, record=item)
                                      for line, item in stored]
        if not matching:
            return result("inconclusive", "No matching submission event; completion cannot be determined")
        for _, item in matching:
            if type(item.get("accepted")) is not bool or type(item.get("http_status")) is not int:
                return result("error", "Matching event has invalid accepted or http_status fields")
        accepted = [item for _, item in matching if item["accepted"] is True]
        if accepted and stored:
            if any(item["http_status"] != 200 or item.get("persisted") is False for item in accepted):
                return result("inconclusive", "Acceptance event contains conflicting persistence or HTTP evidence")
            return result("completed", "Matching backend acceptance and saved record found")
        if accepted or stored:
            return result("inconclusive", "Acceptance event and saved record do not corroborate each other")
        return result("not_completed", "Matching backend submission was not accepted; no matching saved record found")
    except (OSError, ValueError, TypeError) as exc:
        return result("error", f"{type(exc).__name__}: {exc}")
