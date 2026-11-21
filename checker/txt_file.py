"""Read-only TXT validation for the runner's existing file cases."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def check(task_id, evidence_root):
    """Validate destination contents against manifest.token; no GUI actions."""
    evidence = {"task_id": task_id, "manifest": "manifest.json"}

    def result(status, reason):
        evidence["reason"] = reason
        return {"status": status, "evidence": evidence,
                "checked_at": datetime.now(timezone.utc).isoformat()}

    try:
        if not isinstance(task_id, str) or not task_id:
            return result("error", "task_id must be a nonempty string")
        root = Path(evidence_root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
        if not isinstance(manifest, dict) or manifest.get("run_id") != task_id:
            return result("error", "Invalid manifest or task_id does not match manifest.run_id")
        if manifest.get("case") not in {"file_success", "file_failure"}:
            return result("error", "Unsupported TXT case")
        for key in ("destination", "token"):
            if not isinstance(manifest.get(key), str) or not manifest[key]:
                return result("error", f"Missing or invalid manifest field: {key}")
        path = Path(manifest["destination"])
        if not path.is_absolute():
            path = root / path
        evidence.update(path=str(path.absolute()), expected_content=manifest["token"],
                        file_exists=path.is_file(), content_matches=False)
        if path.suffix.lower() != ".txt":
            return result("error", "TXT checker requires a .txt destination; DOCX/PDF are not supported")
        if not path.exists():
            return result("not_completed", "No output exists at the configured destination; this does not prove a save attempt or error recognition")
        if not path.is_file():
            return result("not_completed", "Configured destination is not a regular file")
        data = path.read_bytes()
        evidence.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        # A BOM takes precedence: arbitrary UTF-8 bytes must not be decoded as UTF-16.
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            encodings = ("utf-16",)
        elif data.startswith(b"\xef\xbb\xbf"):
            encodings = ("utf-8-sig",)
        else:
            encodings = ("utf-8", "gb18030")
        for encoding in encodings:
            try:
                content = data.decode(encoding)
                break
            except UnicodeError:
                continue
        else:
            return result("inconclusive", "Output could not be decoded using supported TXT encodings")
        matches = content.rstrip("\r\n") == manifest["token"]
        evidence.update(encoding=encoding, content_matches=matches,
                        comparison="Exact token match after removing trailing CR/LF only")
        return result("completed" if matches else "not_completed",
                      "TXT content matches the task token" if matches else "TXT content does not match the task token")
    except (OSError, ValueError, TypeError) as exc:
        return result("error", f"{type(exc).__name__}: {exc}")
