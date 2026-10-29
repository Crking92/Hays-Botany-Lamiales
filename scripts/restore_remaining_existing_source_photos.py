#!/usr/bin/env python3
"""Restore additional existing Lamiales CC/public-domain photos from staged original bytes.
Preserve all earlier approved gallery entries and leave rights-held originals untouched.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,re,shutil,sys
SRC=Path(sys.argv[1]);ROOT=Path(sys.argv[2]);SITE=ROOT/"site"
path=SITE/"data/reviewed-external-photo-manifest.json"
manifest=json.loads(path.read_text())
assert manifest["schema_version"]==1 and manifest["species"]
index=json.loads((SITE/"data/collection-index.json").read_text())
assert len(index["entries"])==102
licenses={}
def allowed(p):
    value=str(p.get("license") or "").strip()
    if re.search(r"NC|ND|private|unknown|not verified|review|all rights reserved",value,re.I):return None
    if re.fullmatch(r"CC0(?:\s+1\.0)?",value,re.I):
        return ("CC0 1.0","https://creativecommons.org/publicdomain/zero/1.0/")
    if re.fullmatch(r"Public [Dd]omain(?: \(U\.S\. federal work\))?",value,re.I):
        return ("Public Domain","https://creativecommons.org/publicdomain/mark/1.0/")
    m=re.fullmatch(r"CC BY(-SA)? (2\.0|2\.5|3\.0|4\.0)(?: US)?",value,re.I)
    if m:
        lic=("CC BY-SA " if m.group(1) else "CC BY ")+m.group(2)
        url="https://creativecommons.org/licenses/"+("by-sa" if m.group(1) else "by")+"/"+m.group(2)+"/"
        return (lic,url)
    return None
holds={};reasons=Counter();new=0;skipped=0;source_records=0;bytes_total=0
for row in index["entries"]:
    sid,family,genus=row["id"],row["family"],row["genus"]
    assert re.fullmatch(r"[a-z0-9-]+",sid)
    record=SRC/"content/taxa"/family/genus/sid/"species.json"
    assert record.is_file(),sid
    source=json.loads(record.read_text())
    assert source["id"]==sid and source["family"]==family
    existing=manifest["species"].setdefault(sid,[])
    seen_sha={x.get("source_blob_sha") or x.get("original_image_blob_sha") for x in existing}
    seen_sources={x.get("source_page") for x in existing}
    held=[]
    for i,p in enumerate(source.get("images",[]) if isinstance(source.get("images",[]),list) else []):
        source_records+=1
        loc=str(p.get("file") or "")
        why=None
        if not re.fullmatch(r"images/[A-Za-z0-9._-]+\.(?:jpg|jpeg|png|webp)",loc,re.I):
            why="remote_or_missing_local_image_path"
        lic=allowed(p)
        if not why and not lic:why="license_not_strict_public_or_version_undocumented"
        creator=str(p.get("creator") or "").strip()
        src_page=str(p.get("source_page") or "")
        reuse=str(p.get("public_reuse") or "").lower().strip()
        if not why and (not creator or re.search(r"unknown|unverified|resolve",creator,re.I)):why="creator_unverified"
        if not why and (reuse in ("no","false") or "review" in reuse or "noncommercial" in reuse or "private" in reuse):
            why="publication_permission_unverified"
        if not why and not src_page.startswith("https://commons.wikimedia.org/wiki/File:"):
            if not (src_page.startswith("https://www.inaturalist.org/photos/") and creator=="Glass Root Garden" and reuse=="yes" and
                    "Direct license from photographer" in str(p.get("license_basis") or "") and lic[0]=="CC BY 4.0"):
                why="photo_specific_public_source_unverified"
        if why:
            held.append({"index":i,"reason":why});continue
        candidates=[SRC/"content/taxa"/family/genus/sid/loc,
                    SRC/"migration/private-original-photo-holds"/family/genus/sid/loc]
        rawfile=next((p for p in candidates if p.is_file()),None)
        if rawfile is None:
            held.append({"index":i,"reason":"staged_original_bytes_missing"});continue
        content=rawfile.read_bytes()
        ext=rawfile.suffix.lower()
        correct=(content.startswith(b"\xff\xd8\xff") if ext in (".jpg",".jpeg") else
                 content.startswith(b"\x89PNG\r\n\x1a\n") if ext==".png" else
                 content[:4]==b"RIFF" and content[8:12]==b"WEBP")
        if len(content)<500 or len(content)>25*1024*1024 or not correct:
            held.append({"index":i,"reason":"invalid_file_bytes_or_size"});continue
        blob=hashlib.sha1(b"blob "+str(len(content)).encode()+b"\x00"+content).hexdigest()
        if blob in seen_sha or src_page in seen_sources:
            skipped+=1;continue
        photo_path="media/"+sid+"/source-"+blob[:12]+ext
        target=SITE/photo_path
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==content,"Conflict in public media"
        else:shutil.copyfile(rawfile,target)
        existing.append({
          "src":photo_path,"creator":creator,"license":lic[0],"license_url":lic[1],
          "source_page":src_page,"role":str(p.get("role") or "Original field photo")[:450],
          "source_page_is_exact":True,"noncommercial_only":False,"private_rights_review_only":False,
          "source_blob_sha":blob,
          "modified":"Exact original source bytes, not altered",
          "rights_note":"Existing historically sourced public-license photograph",
          "original_source_record":"content/taxa/"+family+"/"+genus+"/"+sid+"/species.json"
        })
        seen_sha.add(blob);seen_sources.add(src_page)
        new+=1;bytes_total+=len(content)
    if held:
        holds[sid]=held
        for reason in held:reasons[reason["reason"]]+=1
    if not existing:manifest["species"].pop(sid,None)
assert new>=0 and len(manifest["species"])<=102
manifest["status"]="EXISTING_SOURCE_CC_GALLERY_RESTORATION_PASS"
manifest["note"]="All entries are pre-existing license-screened source photographs. Originals are preserved; source-specific held records remain in the transfer report."
path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
all_photos=[p for group in manifest["species"].values() for p in group]
local=[p for p in all_photos if p["src"].startswith("media/")]
localpaths={SITE/p["src"] for p in local}
actual={p for p in (SITE/"media").rglob("*") if p.is_file()}
assert localpaths==actual,"Untracked/unapproved file found in public site media"
report={"status":"PASS_RESTORED_ONLY_EXISTING_SOURCE_PHOTOS","source_photo_records":source_records,
        "new_verified_source_copies":new,"already_released_source_records":skipped,
        "all_approved_gallery_references":len(all_photos),
        "all_approved_github_hosted_images":len(local),
        "all_photographed_species":len(manifest["species"]),
        "held_source_records":sum(reasons.values()),"held_by_reason":dict(reasons),"held_by_species":holds,
        "new_photos_collected":0,"source_branch_modified":False,"original_hub_modified":False,
        "source_image_bytes_copied":bytes_total}
(SITE/"photo-source-migration-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
(SITE/"PHOTO_PUBLICATION_SCOPE.md").write_text(
 f"# Lamiales — existing-photo gallery restoration\n\n{len(all_photos)} approved source-photo references "
 f"across {len(manifest['species'])} species, including {len(local)} exact, licensed images in site/media. "
 f"This pass added {new} already-archived photographs from family staging. "
 f"{sum(reasons.values())} source image records remain excluded from public galleries. "
 "No new photos were collected. See photo-source-migration-report.json for reasons.\n")
print("LAMIALES_EXISTING_PHOTO_RESTORE_PASS",json.dumps({k:v for k,v in report.items() if k not in ("held_by_reason","held_by_species")},sort_keys=True),flush=True)
