"""Read-only DOC/DOCX/PDF checks with task-specific expectations."""
import hashlib
import io
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def check(task_id, evidence_root):
    evidence = {"task_id": task_id, "manifest": "manifest.json"}

    def result(status, reason):
        evidence["reason"] = reason
        return {"status": status, "evidence": evidence,
                "checked_at": datetime.now(timezone.utc).isoformat()}

    try:
        root = Path(evidence_root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
        if not isinstance(task_id, str) or not task_id or not isinstance(manifest, dict) or manifest.get("run_id") != task_id:
            return result("error", "Invalid task_id or manifest.run_id mismatch")
        if manifest.get("case") not in {"file_success", "file_failure"}:
            return result("error", "Unsupported document case")
        destination = manifest.get("destination")
        if not isinstance(destination, str) or not destination:
            return result("error", "Missing or invalid destination")
        path = Path(destination)
        if not path.is_absolute():
            path = root / path
        suffix = path.suffix.lower()
        if suffix not in {".docx", ".doc", ".pdf"}:
            return result("error", "Only DOC, DOCX and PDF are supported")
        expected = manifest.get("expected_content")
        if not isinstance(expected, list) or not expected or any(not isinstance(s, str) or not s.strip() for s in expected):
            return result("error", "expected_content must be a nonempty list of nonblank strings")
        pages = manifest.get("expected_pages")
        if pages is not None and (suffix != ".pdf" or type(pages) is not int or pages < 1):
            return result("error", "expected_pages is a positive integer for PDF only")
        evidence.update(path=str(path.absolute()), format=suffix[1:], expected_content=expected,
                        file_exists=path.is_file(), expected_pages=pages)
        if not path.is_file():
            return result("not_completed", "Destination is missing or not a regular file; no save attempt is inferred")
        data = path.read_bytes()
        evidence.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        if not data:
            return result("not_completed", "Document is empty")
        try:
            if suffix == ".docx":
                from docx import Document
            elif suffix == ".pdf":
                from pypdf import PdfReader
        except ImportError as exc:
            return result("error", f"Missing checker dependency: {exc}")
        try:
            if suffix == ".docx":
                document = Document(io.BytesIO(data))
                # Match the existing checker's body-paragraph scope.
                paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
                missing = [s for s in expected if s not in paragraphs]
                evidence.update(comparison="Exact body-paragraph matches; tables/headers excluded",
                                paragraph_count=len(paragraphs))
            elif suffix == ".doc":
                configured = os.environ.get("ANTIWORD_EXE")
                extractor = configured or shutil.which("antiword")
                if not extractor:
                    return result("inconclusive", "Configure ANTIWORD_EXE or install antiword on PATH")
                executable = Path(extractor).expanduser().resolve()
                evidence["extractor"] = str(executable)
                if not executable.is_file():
                    return result("inconclusive", "Configured antiword executable does not exist")
                env = os.environ.copy()
                mapping = os.environ.get("ANTIWORDHOME")
                if mapping:
                    mapping_dir = Path(mapping).expanduser().resolve()
                    if not (mapping_dir / "UTF-8.txt").is_file():
                        return result("inconclusive", "ANTIWORDHOME must contain UTF-8.txt")
                    env["ANTIWORDHOME"] = str(mapping_dir)
                else:
                    # Portable Windows packages resolve ../share/antiword from cwd.
                    mapping_dir = executable.parent.parent / "share" / "antiword"
                    if (mapping_dir / "UTF-8.txt").is_file():
                        env["ANTIWORDHOME"] = str(mapping_dir)
                    elif os.name == "nt":
                        return result("inconclusive", "Missing antiword share/antiword/UTF-8.txt; configure ANTIWORDHOME")
                try:
                    extracted = subprocess.run(
                        [str(executable), "-m", "UTF-8.txt", "-w", "0", str(path.absolute())],
                        cwd=str(executable.parent), env=env, capture_output=True, timeout=30)
                except OSError as exc:
                    return result("inconclusive", f"Cannot launch antiword: {exc}")
                diagnostic = extracted.stderr.decode("utf-8", errors="replace")[:4000]
                evidence.update(extractor_returncode=extracted.returncode, extractor_stderr=diagnostic)
                if extracted.returncode:
                    if any(marker in diagnostic.lower() for marker in
                           ("mapping file", "mappingfile", "home directory", "permission denied")):
                        return result("inconclusive", "Antiword environment configuration failed; see extractor_stderr")
                    return result("not_completed", "DOC cannot be parsed by antiword; see extractor_stderr")
                text = " ".join(extracted.stdout.decode("utf-8").split())
                if not text:
                    return result("inconclusive", "No extractable DOC text")
                missing = [s for s in expected if " ".join(s.split()) not in text]
                evidence["comparison"] = "DOC text substrings with whitespace normalized; antiword"
            else:
                reader = PdfReader(io.BytesIO(data), strict=True)
                if reader.is_encrypted:
                    return result("inconclusive", "Encrypted PDF is not supported")
                evidence["page_count"] = len(reader.pages)
                text = " ".join(" ".join(p.extract_text() or "" for p in reader.pages).split())
                missing = [s for s in expected if " ".join(s.split()) not in text]
                evidence["comparison"] = "Text substrings with whitespace normalized; no OCR"
                if not text:
                    return result("inconclusive", "No extractable PDF text; image-only PDFs require other evidence")
            evidence.update(missing_content=missing, content_matches=not missing)
        except subprocess.TimeoutExpired:
            return result("inconclusive", "DOC extraction timed out")
        except Exception as exc:
            return result("not_completed", f"Document cannot be parsed or inspected: {type(exc).__name__}: {exc}")
        if missing:
            return result("not_completed", "Required document content is missing")
        if suffix == ".pdf" and pages is not None and evidence["page_count"] != pages:
            return result("not_completed", "PDF page count does not match expected_pages")
        return result("completed", "Document is readable and required content matches")
    except (OSError, ValueError, TypeError) as exc:
        return result("error", f"{type(exc).__name__}: {exc}")
