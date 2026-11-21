"""Read-only result checking adapter for the shared UFO runner."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .web_submit import check as check_web
from .txt_file import check as check_txt
from .document_file import check as check_document


def check(task_id, evidence_root):
    """Dispatch existing web and TXT tasks using their manifest case."""
    try:
        manifest = json.loads((Path(evidence_root) / "manifest.json").read_text(encoding="utf-8-sig"))
        if isinstance(manifest, dict) and manifest.get("case") in {"file_success", "file_failure"}:
            destination = manifest.get("destination")
            suffix = Path(destination).suffix.lower() if isinstance(destination, str) else ""
            if suffix in {".docx", ".doc", ".pdf"}:
                return check_document(task_id, evidence_root)
            return check_txt(task_id, evidence_root)
        return check_web(task_id, evidence_root)
    except (OSError, ValueError, TypeError) as exc:
        return {"status": "error", "evidence": {"task_id": task_id, "reason": f"{type(exc).__name__}: {exc}"},
                "checked_at": datetime.now(timezone.utc).isoformat()}

__all__ = ["check"]
