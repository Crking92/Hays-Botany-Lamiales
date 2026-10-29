#!/usr/bin/env python3
"""Existing-sources-only family learner builder for public GitHub Pages.

- Reads exact existing staged species.json records + validated staged collection index
- Publishes only text distilled from those botanical cards, with no source image bytes,
  image URLs, private author permissions, custom HTML, or private quarantine files
- Writes each summarized teaching card and searchable index to website/site/data
- Does not modify historical source, existing photo originals or photo licenses
- Does not change any repository visibility, Pages settings, or hub routing
"""
from __future__ import annotations
import json,re,sys,hashlib
from pathlib import Path
from collections import Counter

SRC=Path(sys.argv[1]).resolve()
DEST=Path(sys.argv[2]).resolve()
assert SRC!=DEST
CONFIG=json.loads((DEST/"config/collection.json").read_text())
INDEX=json.loads((SRC/"data/collection-index.json").read_text())
assert INDEX["collection_id"]==CONFIG["collection_id"]
assert INDEX["authority"]=="STAGING_ONLY"
assert CONFIG["publication"]["enabled"] is False
assert set(CONFIG["family_assignments"])
assert len(INDEX["entries"])==CONFIG["installed_species_baseline"]
SLUG=re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
safe=lambda s:re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]","",str(s or "")).strip()[:5000]
def clean_trait(k,v):
    if isinstance(v,str) and v.strip():return {"label":safe(k).replace("_"," ").capitalize()[:100],"text":safe(v)}
    return None
cards=[];rows=[];counts=Counter()
for row in INDEX["entries"]:
    sid=row["id"];family=row["family"];genus=row["genus"]
    assert SLUG.fullmatch(sid) and family in CONFIG["family_assignments"]
    assert re.fullmatch(r"[A-Z][a-zA-Z-]*",genus)
    expected=f"content/taxa/{family}/{genus}/{sid}/species.json"
    assert row["path"]==expected
    raw=(SRC/expected).read_bytes()
    card=json.loads(raw)
    assert card["id"]==sid and card["family"]==family and card["genus"]==genus
    assert not card.get("scientific_name") or row["scientific_name"]==card["scientific_name"]
    if row.get("common_name") and card.get("common_name") and row["common_name"]!=card["common_name"]:raise AssertionError(f"Name changed: {sid}")
    traitdata=card.get("morphology_keys") or {}
    traits=[]
    if isinstance(traitdata,dict):
        for key,val in traitdata.items():
            if key=="best_field_traits" and isinstance(val,list):
                for v in val[:12]:
                    if isinstance(v,str) and v.strip():traits.append({"label":"Identification","text":safe(v)})
            elif isinstance(val,str) and key not in ("comparison_training",):
                t=clean_trait(key,val)
                if t:traits.append(t)
    if len(traits)>14:traits=traits[:14]
    differences=safe(traitdata.get("comparison_training","")) if isinstance(traitdata,dict) else ""
    lookalikes=card.get("lookalikes") or card.get("look_alikes") or []
    if isinstance(lookalikes,dict):
        names=lookalikes.get("names") or []
        names=[safe(x) for x in names[:10]] if isinstance(names,list) else []
    elif isinstance(lookalikes,list):
        names=[safe(x.get("scientific_name") or x.get("name") or "") if isinstance(x,dict) else safe(x) for x in lookalikes[:10]]
    else:names=[]
    public={
        "id":sid,"family":family,"genus":genus,
        "scientific_name":safe(card.get("scientific_name") or row["scientific_name"]),
        "common_name":safe(card.get("common_name") or row.get("common_name") or card.get("scientific_name") or row["scientific_name"]),
        "look_here_first":safe(card.get("look_here_first")),
        "key_traits":traits,
        "lookalikes":{"names":[n for n in names if n],"differences":differences},
        "verified_photos":[],
        "photo_status":"NOT_INCLUDED_IN_RIGHTS_FILTERED_TEXT_PREVIEW",
        "original_species_sha256":hashlib.sha256(raw).hexdigest(),
        "source_credit":"Existing Hays Botany species record and scientific source notes; original full record retained in assigned family staging branch"
    }
    assert not any(k in public for k in ("images","source_page","photo","media","file","license","permissions"))
    cards.append(public)
    rows.append({k:public[k] for k in ("id","family","genus","scientific_name","common_name")})
    counts[family]+=1
assert len({c["id"] for c in cards})==len(cards)==CONFIG["installed_species_baseline"]
assert sum(counts.values())==len(cards)
site=DEST/"site"
data=site/"data"
target=data/"species"
target.mkdir(parents=True,exist_ok=True)
for p in target.glob("*.json"):
    if p.stem not in {c["id"] for c in cards}:p.unlink()
for card in cards:
    (target/(card["id"]+".json")).write_text(json.dumps(card,ensure_ascii=False,indent=2)+"\n")
(data/"collection-index.json").write_text(json.dumps({"schema_version":1,"collection_id":CONFIG["collection_id"],
   "site_release_stage":"PUBLIC_TEXT_ONLY_PREVIEW_PHOTOS_HELD",
   "entries":rows},ensure_ascii=False,indent=2)+"\n")
(data/"collection-meta.json").write_text(json.dumps({"repository_full_name":CONFIG["repository_full_name"],
   "family_assignments":CONFIG["family_assignments"],
   "site_release_stage":"PUBLIC_TEXT_ONLY_PREVIEW_PHOTOS_HELD"},ensure_ascii=False,indent=2)+"\n")
# Preserve an independently reviewed existing-source photo link without
# copying any of the rights-held staging/source image bytes into the public build.
pilot_path=data/"reviewed-external-photo-manifest.json"
approved=[]
hosted=0
externally_linked=0
if pilot_path.exists():
    pilot=json.loads(pilot_path.read_text(encoding="utf-8"))
    assert pilot.get("schema_version")==1 and isinstance(pilot.get("species"),dict)
    known_ids={c["id"] for c in cards}
    allowed_licenses={
        "CC BY 2.0":"https://creativecommons.org/licenses/by/2.0/",
        "CC BY 3.0":"https://creativecommons.org/licenses/by/3.0/",
        "CC BY 4.0":"https://creativecommons.org/licenses/by/4.0/",
        "CC BY-SA 2.0":"https://creativecommons.org/licenses/by-sa/2.0/",
        "CC BY-SA 3.0":"https://creativecommons.org/licenses/by-sa/3.0/",
        "CC BY-SA 4.0":"https://creativecommons.org/licenses/by-sa/4.0/",
        "Public Domain (U.S. federal work)":"https://creativecommons.org/publicdomain/mark/1.0/",
        "Public Domain":"https://creativecommons.org/publicdomain/mark/1.0/",
    }
    for sid,photos in pilot["species"].items():
        assert sid in known_ids and isinstance(photos,list) and photos
        for p in photos:
            assert p.get("creator") and p.get("role") and p.get("source_page")
            assert p.get("license") in allowed_licenses
            assert p.get("license_url")==allowed_licenses[p["license"]]
            assert p.get("noncommercial_only") is False and p.get("private_rights_review_only") is False
            src=p.get("src","")
            source=p["source_page"]
            if src.startswith("media/"):
                assert re.fullmatch(r"media/[a-z0-9-]+/[A-Za-z0-9._-]+\.(jpg|png)",src,re.I)
                assert src.startswith("media/"+sid+"/")
                photo_path=site/src
                assert photo_path.is_file(),f"Missing approved website image: {src}"
                raw=photo_path.read_bytes()
                assert raw.startswith((b"\xff\xd8\xff",b"\x89PNG\r\n\x1a\n")),f"Image bytes invalid: {src}"
                git_sha=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()
                assert git_sha==p.get("source_blob_sha"),f"Source image byte SHA mismatch: {src}"
                hosted+=1
            else:
                assert src.startswith(("https://upload.wikimedia.org/wikipedia/commons/","https://commons.wikimedia.org/wiki/Special:Redirect/file/"))
                externally_linked+=1
            if source.startswith("https://commons.wikimedia.org/wiki/File:"):
                pass
            else:
                assert source.startswith("https://www.inaturalist.org/photos/") and p["creator"]=="Glass Root Garden"
                assert "Direct reuse permission" in p.get("rights_note",""),"Public owner grant must be explicit"
            approved.append((sid,p))
notice=site/"PHOTO_PUBLICATION_SCOPE.md"
if approved:
    notice.write_text(
       "# Hays Botany - rights-filtered photographed species gallery\n\n"
       f"This public family site includes **{len(cards)} teaching summaries** and **{len(approved)} "
       f"individually attributed photographs across {len(set(sid for sid,p in approved))} species**. "
       f"**{hosted}** photographs are stored as exact byte-verified JPEG/PNG files under "
       f"the site's media directory; **{externally_linked}** approved Commons photos "
       "are linked from Wikimedia rather than copied.\n\n"
       "Only source-specific public-domain, Creative Commons, or original-photographer "
       "approved images are included. No unreviewed quarantine media were promoted. "
       "Photographer, exact source and license appear on every visible species gallery image. "
       "Attribution and anatomical image suitability remain independently reviewable; "
       "photographs alone do not mean anatomy arrows and lessons are complete.\n\n"
       "The source-only cards and excluded historical image records remain preserved. "
       "The original learner is still a fallback.\n",encoding="utf-8")
else:
    notice.write_text("# Hays Botany family text-only learner preview\n\n"
       f"{len(cards)} teaching summaries are available; no images have passed "
       "the individual public-media rights gate yet. The original learner remains "
       "available as a fallback.\n",encoding="utf-8")
report={"status":"PASS_EXISTING_TEXT_WITH_RIGHTS_FILTERED_GALLERY","collection":CONFIG["collection_id"],
 "source_species":len(cards),"published_site_species":len(cards),
 "distinct_families":len(counts),"external_photos_downloaded":0,
 "embedded_original_photo_files":hosted,"site_media_source_sha_verified":hosted,
 "external_commons_photo_links":externally_linked,"approved_photo_species":len(set(sid for sid,p in approved)),
 "private_photo_quarantine_files_copied":0,
 "photo_claimed_publicly_permitted_without_review":0,
 "existing_public_cc_photo_links":len(approved),
 "family_pages_ready_for_text_browsing":True,"original_hub_modified":False,
 "source_family_branch_modified":False,"new_plant_installations":0}
(DEST/"site-build-text-only-report.json").write_text(json.dumps(report,indent=2)+"\n")
print("HAYS_SAFE_TEXT_SITE_BUILD_PASS",json.dumps(report,sort_keys=True))
