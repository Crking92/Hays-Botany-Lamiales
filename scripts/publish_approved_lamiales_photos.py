#!/usr/bin/env python3
"""Rights-checked, idempotent approved-photo publisher for Lamiales' photo manifest.

Unlike the standard families, this site renders reviewed-external-photo-manifest.json.
Preserves the two external licensed links and all existing hosted photos.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from publish_approved_family_photos import read_approved, load, save, blob_sha, fail

def run(source:Path,site:Path,check:bool=False):
    inbox=source/"photo-intake/approved"
    if not inbox.exists():
        print(json.dumps({"status":"NO_APPROVED_INTAKE","installed":0}))
        return
    if inbox.is_symlink() or not inbox.is_dir():fail("Unsafe intake folder")
    for item in inbox.rglob("*"):
        if item.is_symlink():fail("Symlinks forbidden")
        if item.is_file() and item.suffix.lower() in {".jpg",".jpeg",".png",".webp"}:
            if not item.with_name(item.name+".json").is_file():fail("Image without approval sidecar: "+str(item))
        if item.is_file() and item.name.endswith(".json"):
            if not item.with_suffix("").is_file():fail("Approval without source image: "+str(item))
    catalog_path=site/"data/collection-index.json"
    manifest_path=site/"data/reviewed-external-photo-manifest.json"
    gallery_path=site/"data/gallery-index.json"
    catalog=load(catalog_path)
    manifest=load(manifest_path)
    meta=load(site/"data/collection-meta.json")
    entries=catalog["entries"]
    mapping={r["id"]:r for r in entries}
    if len(entries)!=102 or len(mapping)!=102 or meta["repository_full_name"]!="Crking92/Hays-Botany-Lamiales":
        fail("Unexpected Lamiales release inventory")
    if manifest["schema_version"]!=1 or not isinstance(manifest["species"],dict):
        fail("Unrecognized photo manifest")
    if any(v.get("family") not in meta["family_assignments"] for v in entries):
        fail("Family in wrong repository")
    updated_cards={}
    writes=[]
    added=[]
    for sidecar in sorted(inbox.glob("*/*.json")):
        sid=sidecar.parent.name
        if sid not in mapping:fail("New species needs an indexed source card: "+sid)
        approval,image,payload,checksum=read_approved(source,sid,sidecar)
        dst=site/"media"/sid/image.name
        if not dst.resolve().is_relative_to((site/"media").resolve()):fail("Unsafe destination path")
        if dst.exists() and (dst.is_symlink() or dst.read_bytes()!=payload):
            fail("Existing photo filename collision")
        src="media/"+sid+"/"+image.name
        current=manifest["species"].setdefault(sid,[])
        old=next((p for p in current if p.get("src")==src),None)
        if old:
            if old.get("source_blob_sha")!=blob_sha(payload) or old.get("creator")!=approval["creator"] or old.get("license")!=approval["license"]:
                fail("Published image identity/credit drift: "+src)
            if not dst.is_file():fail("Photo manifest references missing bytes")
            continue
        if any(p.get("source_blob_sha")==blob_sha(payload) for p in current):
            fail("Exact image already published under a different filename")
        card_path=site/"data/species"/(sid+".json")
        if sid not in updated_cards:updated_cards[sid]=load(card_path)
        card=updated_cards[sid]
        if card["id"]!=sid or card["family"] not in meta["family_assignments"]:
            fail("Species identity drift")
        photo={"src":src,"creator":approval["creator"].strip(),"source_page":approval["source_page"],
               "source_page_is_exact":True,"license":approval["license"],
               "license_url":approval["license_url"],"source_blob_sha":blob_sha(payload),
               "role":approval["role"].strip(),"modified":approval.get("modifications") or "Original credited",
               "noncommercial_only":False,"private_rights_review_only":False,
               "photo_approved_by":approval["approved_by"],"photo_approval_note":approval["approval_note"],
               "sha256":checksum}
        current.append(photo)
        card.setdefault("verified_photos",[]).append(photo)
        card["photo_status"]="VERIFIED_EXISTING_CC_GALLERY"
        if not dst.exists():writes.append((dst,payload))
        added.append({"species_id":sid,"src":src})
    gallery_entries={}
    for row in entries:
        sid=row["id"]
        photos=manifest["species"].get(sid,[])
        row["photo_count"]=len(photos)
        if sid in updated_cards:
            row["photo_publication_status"]="VERIFIED_EXISTING_CC_GALLERY"
        gallery_entries[sid]={"count":len(photos),"first_src":photos[0]["src"] if photos else None}
    gallery={"schema_version":1,"status":"ONLY_EXISTING_PUBLIC_RIGHTS_CLEARED_SITE_IMAGES",
             "species":len(entries),"photo_count":sum(v["count"] for v in gallery_entries.values()),
             "photo_species":sum(v["count"]>0 for v in gallery_entries.values()),
             "entries":gallery_entries}
    result={"status":"CHECK_PASSED" if check else "PUBLISHED_SITE_SOURCE_UPDATED",
            "installed":len(added),"photo_count":gallery["photo_count"],
            "photo_species":gallery["photo_species"],"added":added}
    if not check:
        for dst,payload in writes:
            dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_bytes(payload)
        if added:
            for sid,card in updated_cards.items():save(site/"data/species"/(sid+".json"),card)
            save(manifest_path,manifest)
            save(catalog_path,catalog)
            save(gallery_path,gallery)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-root",required=True,type=Path)
    ap.add_argument("--site-root",required=True,type=Path)
    ap.add_argument("--check",action="store_true")
    args=ap.parse_args()
    try:run(args.source_root.resolve(),args.site_root.resolve(),args.check)
    except (ValueError,KeyError,TypeError,RuntimeError) as exc:
        print(str(exc),flush=True)
        raise SystemExit(2)
