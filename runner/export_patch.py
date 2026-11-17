"""Export local UFO changes against the preserved official source archive."""
import difflib
import zipfile
from configure import ROOT, REPO

with zipfile.ZipFile(ROOT.parent / "UFO-main.zip") as archive:
    patches = []
    for name in ("ufo/llm/openai.py", "ufo/utils/__init__.py"):
        before = archive.read("UFO-main/" + name).decode().splitlines(True)
        after = (REPO / name).read_text(encoding="utf-8").splitlines(True)
        patches.extend(difflib.unified_diff(before, after, fromfile="a/" + name, tofile="b/" + name))
(ROOT / "ufo-compatibility.patch").write_text("".join(patches), encoding="utf-8")
