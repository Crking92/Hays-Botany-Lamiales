#!/usr/bin/env python3
"""Publish only explicitly approved, already-uploaded family photos.

Source branch contains photo-intake/approved/<species-id>/<file> and <file>.json.
This updates the *existing* public site species card and two gallery indexes,
without changing the historic source library, other plant lessons, or images.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from PIL import Image, UnidentifiedImageError

ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FILENAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,110}\.(?:jpg|jpeg|png|webp)$")
LICENSES = {
    "CC0 1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0/",
    "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-SA 2.0": "https://creativecommons.org/licenses/by-sa/2.0/",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
}
MAX_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 80_000_000

def fail(message: str):
    raise ValueError("APPROVED_PHOTO_INTAKE_BLOCKED: " + message)

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def blob_sha(data: bytes):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def check_image(path: Path):
    if path.is_symlink() or not path.is_file():
        fail("Missing/symlink source image " + str(path))
    if path.stat().st_size > MAX_BYTES or path.stat().st_size < 200:
        fail("Image outside allowed 200-byte to 25-MB size: " + str(path))
    try:
        with Image.open(path) as img:
            if img.width * img.height > MAX_PIXELS:fail("Unreasonably large pixel count")
            if img.format not in {"JPEG","PNG","WEBP"}:
                fail("Unsupported real image format for " + str(path))
            if path.suffix.lower() in {".jpg",".jpeg"} and img.format!="JPEG":
                fail("JPEG extension does not match actual bytes: " + str(path))
            if path.suffix.lower()==".png" and img.format!="PNG":
                fail("PNG extension does not match actual bytes: " + str(path))
            if path.suffix.lower()==".webp" and img.format!="WEBP":
                fail("WebP extension does not match actual bytes: " + str(path))
            img.verify()
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:
        fail("Image decode failed: " + str(exc))

def read_approved(staging: Path, sid: str, sidecar: Path):
    data=load(sidecar)
    name=sidecar.name[:-5]  # remove trailing .json
    if not FILENAME.fullmatch(name) or not ID.fullmatch(sid):
        fail("Image file or species ID naming is unsafe: " + str(sidecar))
    if data.get("species_id")!=sid or data.get("photo_file")!=name:
        fail("Species/image name does not match folder and sidecar: " + str(sidecar))
    if data.get("status")!="APPROVED_FOR_PUBLIC_FAMILY_SITE":
        fail("No explicit public publication decision for " + str(sidecar))
    if data.get("rights_approved_for_public") is not True or data.get("taxon_reviewed") is not True:
        fail("Photo lacks both source-rights and botanical identity approvals: " + str(sidecar))
    if not isinstance(data.get("approved_by"),str) or len(data["approved_by"].strip())<3:
        fail("Named human publication approver is required: " + str(sidecar))
    if not isinstance(data.get("approval_note"),str) or len(data["approval_note"].strip())<12:
        fail("Document actual license/taxon review basis in approval_note: " + str(sidecar))
    license_name=data.get("license")
    if license_name not in LICENSES or data.get("license_url")!=LICENSES[license_name]:
        fail("Unsupported, ambiguous, or non-public license: " + str(license_name))
    for key in ("creator","source_page","role"):
        value=data.get(key)
        if not isinstance(value,str) or not value.strip():
            fail("Photo missing " + key + ": " + str(sidecar))
    if not data["source_page"].startswith("https://") or len(data["source_page"])>2000:
        fail("Original exact photo source must be HTTPS")
    if data.get("source_page_is_exact") is not True:
        fail("Must verify an exact individual photo page")
    if data.get("modifications") is not None and not isinstance(data["modifications"],str):
        fail("Invalid modifications field")
    image=sidecar.with_suffix("")
    check_image(image)
    blob=image.read_bytes()
    checksum=hashlib.sha256(blob).hexdigest()
    # If supplied, the caller's checksum must match real source bytes.
    if data.get("sha256") and data["sha256"]!=checksum:
        fail("Uploaded image SHA-256 does not match sidecar: " + str(sidecar))
    return data,image,blob,checksum

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-root",type=Path,required=True)
    parser.add_argument("--site-root",type=Path,required=True)
    parser.add_argument("--check",action="store_true",help="Validate planned changes but do not write")
    args=parser.parse_args()
    root=args.source_root.resolve()
    site=args.site_root.resolve()
    intake=root/"photo-intake"/"approved"
    if not intake.exists():
        print(json.dumps({"status":"NO_APPROVED_INTAKE","installed":0}));return
    if intake.is_symlink() or not intake.is_dir():fail("Unsafe intake directory")
    # Never silently ignore an uploaded image with missing approval/credit sidecar.
    for source_file in intake.rglob("*"):
        if source_file.is_symlink():
            fail("Symlink in public intake: " + str(source_file))
        if source_file.is_file() and source_file.suffix.lower() in {".jpg",".jpeg",".png",".webp"}:
            if not source_file.with_name(source_file.name+".json").is_file():
                fail("Uploaded photo lacks its approved JSON sidecar: " + str(source_file))
        if source_file.is_file() and source_file.name.endswith(".json") and source_file.parent!=intake:
            image_file=source_file.with_suffix("")
            if not image_file.is_file() or image_file.suffix.lower() not in {".jpg",".jpeg",".png",".webp"}:
                fail("Approved sidecar has no matching supported image: " + str(source_file))
    catalog_path=site/"data/collection-index.json"
    gallery_path=site/"data/gallery-index.json"
    catalog=load(catalog_path)
    gallery=load(gallery_path)
    entries=catalog["entries"]
    by_id={e["id"]:e for e in entries}
    site_meta=load(site/"data/collection-meta.json")
    families=set(site_meta["family_assignments"])
    site_repo=site_meta["repository_full_name"].split("/")[-1]
    if not families or not site_repo.startswith("Hays-Botany-"):
        fail("Unrecognized assigned family repository")
    if len(by_id)!=len(entries) or len(entries)!=gallery["species"] or set(gallery["entries"])!=set(by_id):
        fail("Family site inventory changed; manual release review required")
    if any(row.get("family") not in families for row in entries):
        fail("Species belongs to an unassigned family in the destination site")
    if gallery["status"]!="ONLY_EXISTING_PUBLIC_RIGHTS_CLEARED_SITE_IMAGES":
        fail("Unknown rights policy for target site")
    # Stage everything in process memory before writing anything.
    changed_cards={}
    writes=[]
    added=[]
    for sidecar in sorted(intake.glob("*/*.json")):
        sid=sidecar.parent.name
        if sid not in by_id or by_id[sid]["family"] not in families:
            fail("Cannot publish a species not yet on the assigned family site: " + sid)
        meta,image,payload,sha256=read_approved(root,sid,sidecar)
        dest=site/"media"/sid/image.name
        if not dest.resolve().is_relative_to((site/"media").resolve()):
            fail("Unsafe target media path")
        card_path=site/"data/species"/(sid+".json")
        if sid not in changed_cards:
            changed_cards[sid]=load(card_path)
        card=changed_cards[sid]
        if card["id"]!=sid:fail("Species card identity mismatch: " + sid)
        photos=card.get("verified_photos")
        if not isinstance(photos,list):fail("Malformed species photo list")
        src="media/"+sid+"/"+image.name
        if dest.exists():
            if dest.is_symlink() or dest.read_bytes()!=payload:
                fail("Photo collision at " + str(dest))
        existing=next((p for p in photos if p.get("src")==src),None)
        if existing:
            if existing.get("creator")!=meta["creator"] or existing.get("license")!=meta["license"] or existing.get("source_page")!=meta["source_page"]:
                fail("Existing published credit differs: " + src)
            if dest.exists():continue
            fail("Published species card has missing media: " + src)
        if any(p.get("source_blob_sha")==blob_sha(payload) for p in photos):
            fail("This exact photograph already exists under a different name: " + sid)
        record={
            "src":src, "creator":meta["creator"].strip(),
            "source_page":meta["source_page"], "source_page_is_exact":True,
            "license":meta["license"],"license_url":meta["license_url"],
            "source_blob_sha":blob_sha(payload),
            "role":meta["role"].strip(),
            "modified":meta.get("modifications") or "Original source photo credited; no alterations declared",
            "noncommercial_only":False,"private_rights_review_only":False,
            "photo_approval_note":meta["approval_note"],"photo_approved_by":meta["approved_by"],
            "sha256":sha256
        }
        photos.append(record)
        if dest.exists():fail("File already in site media but not referenced in the species lesson: " + src)
        writes.append((dest,payload))
        added.append({"species_id":sid,"src":src,"creator":record["creator"],"license":record["license"]})
    if not added:
        print(json.dumps({"status":"NO_NEW_APPROVED_PHOTOS","installed":0,"species_count":len(by_id)}));return
    counts={}
    for row in entries:
        sid=row["id"]
        card=changed_cards.get(sid)
        if card is None:card=load(site/"data/species"/(sid+".json"))
        photos=card.get("verified_photos",[])
        counts[sid]=len(photos)
        if sid in changed_cards:
            row["photo_count"]=len(photos)
            publication_status=("RELEASED_CC_GALLERY" if site_repo=="Hays-Botany-Asteraceae"
                                else "VERIFIED_EXISTING_CC_GALLERY")
            row["photo_publication_status"]=publication_status
            card["photo_status"]=publication_status
        gallery["entries"][sid]={
            "count":len(photos),
            "first_src":photos[0]["src"] if photos else None
        }
    gallery["photo_count"]=sum(counts.values())
    gallery["photo_species"]=sum(v>0 for v in counts.values())
    gallery["species"]=len(entries)
    report={"status":"CHECK_PASSED" if args.check else "PUBLISHED_SITE_SOURCE_UPDATED",
            "installed":len(added),"species_count":len(entries),
            "photo_count":gallery["photo_count"],"photo_species":gallery["photo_species"],
            "added":added}
    if not args.check:
        for dest,payload in writes:
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(payload)
        for sid,card in changed_cards.items():
            save(site/"data/species"/(sid+".json"),card)
        save(catalog_path,catalog)
        save(gallery_path,gallery)
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    try:main()
    except (ValueError,KeyError,TypeError,RuntimeError) as exc:
        print(str(exc),flush=True)
        raise SystemExit(2)
