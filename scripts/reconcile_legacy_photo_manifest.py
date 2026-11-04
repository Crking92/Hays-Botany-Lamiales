#!/usr/bin/env python3
"""Repair Lamiales verified gallery consistency without altering source archives.

Preserves the first, already published CC image and removes only the redundant
2026-11-04 hand-published byte-identical copy. Incorporates two historically
verified, licensed files into the legacy manifest. This is a no-download
reconciliation; never approves any unlicensed or unknown image.
"""
from pathlib import Path
import hashlib,json

site=Path("site")
mp=site/"data/reviewed-external-photo-manifest.json"
ip=site/"data/collection-index.json"
gp=site/"data/gallery-index.json"
m=json.loads(mp.read_text())
idx=json.loads(ip.read_text())
g=json.loads(gp.read_text())
def jwrite(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
def card(slug):
    p=site/"data/species"/(slug+".json")
    return p,json.loads(p.read_text())
def sha(path):
    b=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def get_single(slug,old):
    p,d=card(slug)
    matches=[x for x in d.get("verified_photos",[]) if x["src"]==old]
    if len(matches)!=1:raise RuntimeError("Expected one certified species image: "+old)
    return p,d,matches[0]

salvia="salvia-engelmannii"
old="media/salvia-engelmannii/historical-wikimedia-5752c76b34f87ec9.jpg"
retained="media/salvia-engelmannii/source-5752c76b34f8.jpg"
sp,scard,legacy=get_single(salvia,old)
assert (site/old).is_file() and (site/retained).is_file()
assert sha(site/old)==sha(site/retained)==legacy["source_blob_sha"]=="5752c76b34f87ec9ac7c5cb321b01927bff57156"
assert len([x for x in m["species"][salvia] if x["src"]==retained and x["source_blob_sha"]==legacy["source_blob_sha"]])==1
legacy["src"]=retained
# If the retained physical file already has its own separate species-card
# entry, keep that entry instead of creating a duplicated photo.
seen=set()
new=[]
for x in scard["verified_photos"]:
    key=x["src"]
    if key not in seen:
        new.append(x);seen.add(key)
scard["verified_photos"]=new
jwrite(sp,scard)

for slug,picture in [
 ("anisacanthus-quadrifidus-var-wrightii","media/anisacanthus-quadrifidus-var-wrightii/archived-735e07d534f90765.jpg"),
 ("phyla-nodiflora","media/phyla-nodiflora/archived-67d68269f0c627b7.jpg"),
]:
    p,d,source=get_single(slug,picture)
    assert source["license"].startswith(("CC BY ","CC BY-SA ","CC0 "))
    assert source["license_url"].startswith("https://creativecommons.org/")
    assert source["creator"] and source["source_page"].startswith("https://")
    assert sha(site/picture)==source["source_blob_sha"]
    rows=m["species"].setdefault(slug,[])
    if not any(x["src"]==picture for x in rows):
        rows.append({
         k:source[k] for k in ("src","creator","license","license_url","source_page",
            "role","source_page_is_exact","noncommercial_only","private_rights_review_only",
            "source_blob_sha","modified")
         })
        rows[-1]["rights_note"]="Existing photo-specific Commons license, credited and hash-checked; legacy manifest reconciliation"
        rows[-1]["original_source_record"]="Existing species gallery card and historical source archive"
jwrite(mp,m)

(site/old).unlink()  # byte-identical EXTRA copy only; retained image remains.

allcards={}
for row in idx["entries"]:
    slug=row["id"];cp,record=card(slug)
    n=len(record.get("verified_photos",[]))
    allcards[slug]=n
    row["photo_count"]=n
    g["entries"][slug]["count"]=n
g["photo_count"]=sum(allcards.values())
g["photo_species"]=sum(n>0 for n in allcards.values())
jwrite(ip,idx)
jwrite(gp,g)

physical={p.relative_to(site).as_posix() for p in (site/"media").rglob("*") if p.is_file()}
approved={p["src"] for group in m["species"].values() for p in group if p["src"].startswith("media/")}
if physical!=approved:raise RuntimeError("Untracked/missing image assets: "+str(sorted(physical^approved)[:12]))
for slug in allcards:
    cp,d=card(slug)
    for p in d.get("verified_photos",[]):
        if p["src"].startswith("media/"):
            file=site/p["src"]
            if not file.is_file() or sha(file)!=p["source_blob_sha"]:
                raise RuntimeError("Missing/mismatched species card image: "+slug+" "+p["src"])
print("LAMIALES_LEGACY_MANIFEST_RECONCILED",json.dumps({"physical_photos":len(physical),"gallery_photos":g["photo_count"],"legacy_manifest_photos":len(approved),"replacement_salvia_source":retained,"original_source_preserved":True}),flush=True)
