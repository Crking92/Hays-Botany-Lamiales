#!/usr/bin/env python3
"""Append verified family-card photographs to the Lamiales PUBLIC display manifest.

Lamiales app.js renders reviewed-external-photo-manifest.json, not the species
card photo arrays. Never replace/remove an existing approved manifest photo.
Rebuild only the two display counts from that merged, preserved manifest.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(path: Path, data):
    temp = path.with_name(path.name + ".merge-new")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)

def git_blob(b: bytes):
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", type=Path, default=Path("site"))
    a = parser.parse_args()
    site = a.site_root
    idxfile = site / "data/collection-index.json"
    galfile = site / "data/gallery-index.json"
    photofile = site / "data/reviewed-external-photo-manifest.json"
    idx, gal, manifest = map(read, (idxfile, galfile, photofile))
    meta = read(site / "data/collection-meta.json")
    if meta.get("repository_full_name") != "Crking92/Hays-Botany-Lamiales":
        raise SystemExit("Wrong family repository")
    rows = idx["entries"]
    IDs = [r["id"] for r in rows]
    if len(IDs) != len(set(IDs)) or set(IDs) != set(manifest["species"]) or set(IDs) != set(gal["entries"]):
        raise SystemExit("Display manifest, species list, or gallery index changed unexpectedly")
    if gal["status"] != "ONLY_EXISTING_PUBLIC_RIGHTS_CLEARED_SITE_IMAGES":
        raise SystemExit("Unknown public photo-rights gate")
    new = []
    skipped = 0
    for row in rows:
        sid = row["id"]
        card = read(site / "data/species" / (sid + ".json"))
        if card["id"] != sid or card["family"] != row["family"]:
            raise SystemExit("Species card identity mismatch " + sid)
        photos = manifest["species"][sid]
        if not isinstance(photos, list):
            raise SystemExit("Malformed public photo list " + sid)
        existing_src = {p.get("src") for p in photos}
        existing_hash = {p.get("source_blob_sha") for p in photos if p.get("source_blob_sha")}
        existing_sha = {p.get("sha256") for p in photos if p.get("sha256")}
        existing_source = {p.get("source_page") for p in photos if p.get("source_page")}
        for p in card.get("verified_photos", []):
            src = p.get("src", "")
            if src in existing_src:
                skipped += 1
                continue
            if (p.get("source_blob_sha") and p.get("source_blob_sha") in existing_hash) or (p.get("sha256") and p.get("sha256") in existing_sha):
                skipped += 1
                continue
            if p.get("source_page") in existing_source:
                skipped += 1
                continue
            rel = PurePosixPath(src)
            if len(rel.parts) < 3 or rel.parts[0] != "media" or rel.parts[1] != sid or ".." in rel.parts:
                raise SystemExit("Untrusted photo path " + str(src))
            img = site.joinpath(*rel.parts)
            if not img.is_file() or img.is_symlink():
                raise SystemExit("Approved photo bytes missing: " + src)
            if any(not p.get(k) for k in ("creator", "license", "license_url", "source_page", "source_blob_sha")):
                raise SystemExit("Approved photo lacks individual source/rights details: " + src)
            if p.get("private_rights_review_only") or p.get("photo_approval_mode") not in ("OWNER_STANDING_PHOTO_FIRST_POLICY", "NAMED_HUMAN_PHOTO_REVIEW"):
                raise SystemExit("Photo has no valid public approval: " + src)
            nc = p["license"] in ("CC BY-NC 4.0", "CC BY-NC-SA 4.0")
            if p.get("noncommercial_only") is not nc:
                raise SystemExit("Incorrect photo noncommercial restriction flag: " + src)
            if nc and meta.get("photo_license_policy", {}).get("noncommercial_educational_use") is not True:
                raise SystemExit("NC-only photo cannot be published here")
            binary = img.read_bytes()
            if git_blob(binary) != p["source_blob_sha"] or (p.get("sha256") and hashlib.sha256(binary).hexdigest() != p["sha256"]):
                raise SystemExit("Media bytes differ from approved photo source: " + src)
            photos.append(p)
            existing_src.add(src)
            existing_hash.add(p["source_blob_sha"])
            if p.get("sha256"): existing_sha.add(p["sha256"])
            existing_source.add(p["source_page"])
            new.append({"species_id":sid, "src":src})
        row["photo_count"] = len(photos)
        gal["entries"][sid] = {"count":len(photos), "first_src":photos[0]["src"] if photos else None}
        if photos and row.get("photo_publication_status") == "PHOTOS_HELD_FROM_PUBLIC_GALLERY":
            row["photo_publication_status"] = "VERIFIED_EXISTING_CC_GALLERY"
    gal["photo_count"] = sum(len(p) for p in manifest["species"].values())
    gal["photo_species"] = sum(bool(p) for p in manifest["species"].values())
    gal["species"] = len(rows)
    # All references, including previously reviewed Commons links, stay intact.
    if len(new):
        save(photofile, manifest)
    save(idxfile, idx)
    save(galfile, gal)
    print("LAMIALES_PRESERVED_MANIFEST_MERGE", json.dumps({
        "new_approved_photos_linked":len(new),
        "existing_photo_references_retained":gal["photo_count"]-len(new),
        "already_in_manifest_or_duplicate":skipped,
        "visible_photo_count":gal["photo_count"],
        "photographed_species":gal["photo_species"],
        "species":gal["species"],
        "added":new
    },sort_keys=True))

if __name__ == "__main__":
    main()
