#!/usr/bin/env python3
"""Validate and package only the existing rights-filtered family site, never stage archives."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/"site"
DIST=ROOT/"dist"
subprocess.run(["python3",str(ROOT/"scripts/validate_collection.py")],check=True,cwd=ROOT)
catalog=json.loads((SITE/"data/collection-index.json").read_text(encoding="utf-8"))
meta=json.loads((SITE/"data/collection-meta.json").read_text(encoding="utf-8"))
photos=json.loads((SITE/"data/reviewed-external-photo-manifest.json").read_text(encoding="utf-8"))
assert len(catalog["entries"])==102 and meta["repository_full_name"]=="Crking92/Hays-Botany-Lamiales"
ids={r["id"] for r in catalog["entries"]}
assert len(ids)==102
assert photos["schema_version"]==1
approved=0
local=0
for sid,images in photos["species"].items():
    assert sid in ids and images
    for img in images:
        src=img["src"]
        assert img["creator"] and img["license"] and img["license_url"] and img["source_page"]
        assert img["noncommercial_only"] is False and img["private_rights_review_only"] is False
        if src.startswith("media/"):
            assert src.startswith("media/"+sid+"/") and ".." not in src
            p=SITE/src
            assert p.is_file(),src
            data=p.read_bytes()
            assert data.startswith((b"\xff\xd8\xff",b"\x89PNG\r\n\x1a\n")),src
            sha=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
            assert sha==img["source_blob_sha"],src
            local+=1
        else:
            assert src.startswith(("https://commons.wikimedia.org/wiki/Special:Redirect/file/","https://upload.wikimedia.org/wikipedia/commons/")),src
        approved+=1
assert "<meta name=\"robots\" content=\"index,follow\">" in (SITE/"index.html").read_text(encoding="utf-8")
if DIST.exists():shutil.rmtree(DIST)
shutil.copytree(SITE,DIST)
assert len(list((DIST/"data/species").glob("*.json")))==102
assert len([p for p in (DIST/"media").rglob("*") if p.is_file()])==local
print(json.dumps({"status":"RIGHTS_FILTERED_VISUAL_SITE_PREVIEW_PASS","species":102,
                  "approved_photos":approved,"physically_hosted_photos":local,
                  "externally_linked_photos":approved-local,
                  "rights_hold_media_copied":0,"deployment":False},sort_keys=True))
