#!/usr/bin/env python3
"""Surface previously hosted, source-credited Lamiales photos in species galleries.

Copies RECORDS, not pixels. Reuses existing reviewed photo manifest and media.
Do not create rights grants or change archived sources. Fail closed on any
identity, source, license, hash, or gallery inconsistency.
"""
from pathlib import Path
from collections import Counter
import hashlib,json
SITE=Path("site")
mp=SITE/"data/reviewed-external-photo-manifest.json"
ip=SITE/"data/collection-index.json"
gp=SITE/"data/gallery-index.json"
manifest=json.loads(mp.read_text())
index=json.loads(ip.read_text())
gallery=json.loads(gp.read_text())
byid={r["id"]:r for r in index["entries"]}
added=Counter()
holds=Counter()
def gitsha(path):
    data=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def write(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
if set(manifest["species"])!=set(byid):
    raise RuntimeError("Legacy photo manifest species differs from family index")
for slug,records in manifest["species"].items():
    cardpath=SITE/"data/species"/(slug+".json")
    if not cardpath.is_file(): raise RuntimeError("Missing target species card: "+slug)
    card=json.loads(cardpath.read_text())
    if card["id"]!=slug:raise RuntimeError("Taxon card ID mismatch")
    images=card.setdefault("verified_photos",[])
    srcs={p.get("src") for p in images}
    sha_map={p.get("source_blob_sha") for p in images if p.get("source_blob_sha")}
    for r in records:
        source=str(r.get("src") or "")
        if not source.startswith("media/"+slug+"/"):
            # Already indexed remote Commons images remain as links.
            if source.startswith("https://"):
                holds["remote_link_no_binary_migration"]+=1
                continue
            raise RuntimeError("Source image not assigned to this species: "+slug)
        if source in srcs or r.get("source_blob_sha") in sha_map:
            holds["already_gallery_linked_or_exact_binary_duplicate"]+=1
            continue
        path=SITE/source
        if not path.is_file() or gitsha(path)!=r.get("source_blob_sha"):
            raise RuntimeError("Archived published photo bytes fail hash: "+source)
        license=str(r.get("license") or "")
        nc=license in ("CC BY-NC 4.0","CC BY-NC-SA 4.0")
        owner=license=="OWNER PUBLIC DISPLAY PERMISSION"
        if not (license.startswith(("CC BY ","CC BY-SA ","CC BY-NC ","CC BY-NC-SA ","CC0 ")) or owner):
            holds["unsupported_license"]+=1
            continue
        if r.get("noncommercial_only") is not (nc or owner):
            raise RuntimeError("Photo permission flag conflict: "+source)
        if r.get("private_rights_review_only") is not False:
            holds["private_rights_hold"]+=1
            continue
        if not r.get("creator") or not str(r.get("source_page") or "").startswith("https://") or not str(r.get("license_url") or "").startswith("https://"):
            holds["incomplete_source_credits"]+=1
            continue
        photo={k:r[k] for k in
            ("src","creator","license","license_url","source_page","role",
             "noncommercial_only","private_rights_review_only",
             "source_blob_sha","modified") if k in r}
        photo["source_page_is_exact"]=r.get("source_page_is_exact") is True
        photo["photo_approval_mode"]="OWNER_STANDING_PHOTO_FIRST_POLICY"
        photo["photo_approved_by"]="Existing verified, per-image archived-public manifest and byte-matching published original"
        photo["source_review_evidence"]="Existing public family reviewed-photo manifest; unchanged file "+source+"; SHA "+r["source_blob_sha"]
        photo["taxon_review_evidence"]="Original reviewed manifest and matching existing species gallery ID "+slug+"; advanced anatomy review deferred"
        images.append(photo)
        srcs.add(source);sha_map.add(r["source_blob_sha"])
        added[slug]+=1
    if added[slug]:write(cardpath,card)

all_shas=set()
verified_local=set()
for row in index["entries"]:
    slug=row["id"]
    card=json.loads((SITE/"data/species"/(slug+".json")).read_text())
    count=len(card["verified_photos"])
    row["photo_count"]=count
    gallery["entries"][slug]["count"]=count
    for p in card["verified_photos"]:
        src=p.get("src","")
        if not src.startswith("media/"):
            continue
        if not src.startswith("media/"+slug+"/"):raise RuntimeError("Wrong species media path: "+src)
        path=SITE/src
        if not path.is_file() or gitsha(path)!=p.get("source_blob_sha"):
            raise RuntimeError("Gallery entry has missing/mismatched photo: "+src)
        if not p.get("creator") or not p.get("source_page") or not p.get("license_url"):
            raise RuntimeError("Missing gallery attribution: "+src)
        verified_local.add(src)
gallery["photo_count"]=sum(r["photo_count"] for r in index["entries"])
gallery["photo_species"]=sum(r["photo_count"]>0 for r in index["entries"])
write(ip,index);write(gp,gallery)
actual={p.relative_to(SITE).as_posix() for p in (SITE/"media").rglob("*") if p.is_file()}
unlinked=actual-verified_local
known={p["src"]:p for rows in manifest["species"].values() for p in rows if p.get("src","").startswith("media/")}
for source in sorted(unlinked):
    rec=known.get(source)
    if not rec or gitsha(SITE/source)!=rec.get("source_blob_sha"):
        raise RuntimeError("Unverified hosted media not referenced in approved original manifest: "+source)
    slug=source.split("/")[1]
    card=json.loads((SITE/"data/species"/(slug+".json")).read_text())
    if not any(p.get("source_blob_sha")==rec["source_blob_sha"] for p in card["verified_photos"]):
        raise RuntimeError("Missing species-gallery representation of archived duplicate: "+source)
if verified_local-actual:
    raise RuntimeError("Species gallery references absent files")
print("LAMIALES_EXISTING_MEDIA_GALLERY_BACKFILL",json.dumps({
    "new_gallery_links":sum(added.values()),"species_improved":sum(n>0 for n in added.values()),"preserved_verified_duplicate_files":len(unlinked),
    "hosted_photos":len(actual),"gallery_photos":gallery["photo_count"],
    "nonchanges":dict(holds),"by_species":dict(added)
},sort_keys=True),flush=True)
