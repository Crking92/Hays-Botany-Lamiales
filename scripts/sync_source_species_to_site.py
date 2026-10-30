#!/usr/bin/env python3
"""Sync changed approved-source species JSON to assigned live family site, without image changes.

Only the explicitly changed content/taxa/<Family>/<Genus>/<id>/species.json
paths from the registered family staging branch are processed. Family-identity
validation fails closed; no original-hub writes or image permission guesses.
"""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess
from pathlib import Path

SLUG=re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
GENUS=re.compile(r"^[A-Z][A-Za-z-]+$")
def fail(msg):raise ValueError("FAMILY_SPECIES_SYNC_BLOCKED: "+msg)
def read(p):return json.loads(p.read_text(encoding="utf-8"))
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def changed_files(root,previous):
    if not re.fullmatch(r"[0-9a-f]{40}",previous):fail("Expected exact previous Git commit SHA")
    r=subprocess.run(["git","diff","--name-only","--diff-filter=AM",previous,"HEAD","--","content/taxa"],
                     cwd=root,capture_output=True,text=True)
    if r.returncode:fail("Previous source commit unavailable; cannot determine changed species")
    return [x for x in r.stdout.splitlines() if x.endswith("/species.json")]
def compact_traits(raw):
    out=[]
    src=raw.get("morphology_keys")
    if isinstance(src,dict):
        candidates=src.get("best_field_traits") or src.get("field_traits") or []
        if isinstance(candidates,list):
            for item in candidates[:12]:
                if isinstance(item,str) and item.strip():out.append({"label":"Field character","text":item.strip()})
                elif isinstance(item,dict) and item.get("text"):
                    out.append({"label":str(item.get("label") or "Field character"),"text":str(item["text"])})
    if not out and isinstance(raw.get("key_traits"),list):
        for item in raw["key_traits"][:12]:
            if isinstance(item,str) and item.strip():out.append({"label":"Field character","text":item.strip()})
            elif isinstance(item,dict) and item.get("text"):
                out.append({"label":str(item.get("label") or "Field character"),"text":str(item["text"])})
    return out
def render(source,site,files,check=False):
    catalog_path=site/"data/collection-index.json"
    gallery_path=site/"data/gallery-index.json"
    catalog=read(catalog_path);meta=read(site/"data/collection-meta.json")
    entries=catalog["entries"]
    by_id={x["id"]:x for x in entries}
    if len(by_id)!=len(entries) or not meta["repository_full_name"].startswith("Crking92/Hays-Botany-"):
        fail("Unexpected family site")
    families=set(meta["family_assignments"])
    gallery=read(gallery_path) if gallery_path.exists() else None
    if gallery and gallery.get("species")!=len(entries):fail("Existing gallery count mismatch")
    planned=[]
    new_ids=[]
    for name in sorted(set(files)):
        parts=Path(name).parts
        if len(parts)!=6 or parts[:2]!=("content","taxa") or parts[-1]!="species.json":
            fail("Unrecognized source path: "+name)
        _content,_taxa,family,genus,sid,_species=parts
        if family not in families or not GENUS.fullmatch(genus) or not SLUG.fullmatch(sid):
            fail("Source record not assigned to this family site: "+name)
        original=source/name
        if original.is_symlink() or not original.is_file():fail("Missing or symlinked record")
        raw_bytes=original.read_bytes()
        raw=json.loads(raw_bytes)
        if not isinstance(raw,dict) or raw.get("id")!=sid or raw.get("family")!=family or raw.get("genus")!=genus:
            fail("Species path/taxonomy mismatch: "+name)
        scientific=raw.get("scientific_name")
        if not isinstance(scientific,str) or not scientific.strip() or len(scientific)>200:
            fail("Missing validated format scientific name: "+sid)
        common=raw.get("common_name") or scientific
        if not isinstance(common,str) or len(common)>250:fail("Invalid common name")
        status="AUTO_IMPORTED_SOURCE_RECORD_REVIEW_WELCOME"
        card_path=site/"data/species"/(sid+".json")
        current=read(card_path) if card_path.exists() else None
        if current and (current.get("id")!=sid or current.get("family")!=family):
            fail("Existing site species is different taxon: "+sid)
        first=raw.get("look_here_first")
        if not isinstance(first,str):first=""
        comparisons=raw.get("comparisons") or {}
        if not isinstance(comparisons,dict):comparisons={}
        names=comparisons.get("confused_with") or []
        if not isinstance(names,list):names=[]
        morph=raw.get("morphology_keys")\n        if not isinstance(morph,dict):morph={}\n        text=comparisons.get("key_distinctions") or morph.get("comparison_training","")
        if not isinstance(text,str):text=""
        card=dict(current or {})
        card.update({"id":sid,"family":family,"genus":genus,
                     "scientific_name":scientific,"common_name":common,
                     "look_here_first":first.strip(),
                     "key_traits":traits,
                     "lookalikes":{"names":[str(x) for x in names if isinstance(x,str)][:15],
                                    "differences":text},
                     "source_record_sha256":hashlib.sha256(raw_bytes).hexdigest(),
                     "source_sync_status":status})
        card.setdefault("verified_photos",[])
        if not isinstance(card["verified_photos"],list):fail("Existing gallery metadata malformed")
        card.setdefault("photo_status","PHOTOS_HELD_FROM_PUBLIC_GALLERY")
        card.setdefault("source_credit","Family source branch scientific record; automated, review welcome")
        old=by_id.get(sid)
        if old:
            if old.get("family")!=family:fail("Existing site family identity mismatch")
            old.update({"scientific_name":scientific,"common_name":common,"genus":genus})
        else:
            entry={"id":sid,"family":family,"genus":genus,
                   "scientific_name":scientific,"common_name":common,
                   "photo_count":0,"photo_publication_status":"PHOTOS_HELD_FROM_PUBLIC_GALLERY"}
            entries.append(entry);by_id[sid]=entry
            new_ids.append(sid)
            if gallery is not None:
                gallery["entries"][sid]={"count":0,"first_src":None}
        planned.append((card_path,card))
    if new_ids and gallery is not None:gallery["species"]=len(entries)
    result={"status":"CHECK_PASSED" if check else "SITE_SOURCE_RECORDS_UPDATED",
            "changed_species":len(planned),"new_species":len(new_ids),"new_species_ids":new_ids,
            "collection_species":len(entries)}
    if not check and planned:
        for p,card in planned:write(p,card)
        write(catalog_path,catalog)
        if gallery is not None:write(gallery_path,gallery)
    print(json.dumps(result,indent=2))
    return result
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-root",type=Path,required=True)
    ap.add_argument("--site-root",type=Path,required=True)
    ap.add_argument("--changed-from",help="Previous source commit SHA for automatic safe event diff")
    ap.add_argument("--file",action="append",help="One explicitly selected source species path (test/manual)")
    ap.add_argument("--check",action="store_true")
    a=ap.parse_args()
    source=a.source_root.resolve();site=a.site_root.resolve()
    items=changed_files(source,a.changed_from) if a.changed_from else (a.file or [])
    if not items:
        print(json.dumps({"status":"NO_CHANGED_SPECIES","changed_species":0}))
        return
    render(source,site,items,a.check)
if __name__=="__main__":
    try:main()
    except (ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print(str(exc),flush=True)
        raise SystemExit(2)
