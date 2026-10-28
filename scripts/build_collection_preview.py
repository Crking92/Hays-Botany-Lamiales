#!/usr/bin/env python3
"""Build an UNPUBLISHED collection website shell; never includes source media."""
from pathlib import Path
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
subprocess.run(["python3", str(ROOT / "scripts/validate_collection.py")], check=True, cwd=ROOT)
config = json.loads((ROOT / "config/collection.json").read_text(encoding="utf-8"))
index = json.loads((ROOT / "data/collection-index.json").read_text(encoding="utf-8"))
assert config["planning_status"] == "STAGING_ONLY_NOT_AUTHORITATIVE"
assert config["publication"]["enabled"] is False
assert not index["entries"], "A populated collection requires a separate photographic release review"
if DIST.exists():
    shutil.rmtree(DIST)
(DIST / "data").mkdir(parents=True)
for name in ("index.html", "styles.css", "app.js"):
    shutil.copyfile(ROOT / "site" / name, DIST / name)
(DIST / "data/collection-meta.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
(DIST / "data/collection-index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
html = (DIST / "index.html").read_text(encoding="utf-8")
assert '<meta name="robots" content="noindex,nofollow">' in html
assert 'https://crking92.github.io/Hays-County-Botany/' in html
allowed = {"index.html", "styles.css", "app.js", "data/collection-meta.json", "data/collection-index.json"}
actual = {p.relative_to(DIST).as_posix() for p in DIST.rglob("*") if p.is_file()}
assert actual == allowed, (actual, allowed)
print(json.dumps({"status": "UNPUBLISHED_UI_PROTOTYPE_PASS", "files": len(actual),
                  "photos": 0, "botanical_records": 0, "deployment": False}, sort_keys=True))
