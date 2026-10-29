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
approved_external=[]
if pilot_path.exists():
    pilot=json.loads(pilot_path.read_text(encoding="utf-8"))
    assert pilot.get("schema_version")==1 and isinstance(pilot.get("species"),dict)
    known_ids={c["id"] for c in cards}
    for sid,photos in pilot["species"].items():
        assert sid in known_ids and isinstance(photos,list)
        for p in photos:
            assert p["src"].startswith(("https://upload.wikimedia.org/wikipedia/commons/","https://commons.wikimedia.org/wiki/Special:Redirect/file/"))
            assert p["source_page"].startswith("https://commons.wikimedia.org/wiki/File:")
            assert p["creator"].strip() and p["role"].strip()
            allowed_licenses={
                "CC BY 2.0":"https://creativecommons.org/licenses/by/2.0/",
                "CC BY 3.0":"https://creativecommons.org/licenses/by/3.0/",
                "CC BY 4.0":"https://creativecommons.org/licenses/by/4.0/",
                "CC BY-SA 3.0":"https://creativecommons.org/licenses/by-sa/3.0/",
                "CC BY-SA 4.0":"https://creativecommons.org/licenses/by-sa/4.0/",
                "Public Domain (U.S. federal work)":"https://creativecommons.org/publicdomain/mark/1.0/"
            }
            assert p["license"] in allowed_licenses and p["license_url"]==allowed_licenses[p["license"]]
            assert p["private_rights_review_only"] is False
            assert p["noncommercial_only"] is False
            approved_external.append((sid,p))
notice=site/"PHOTO_PUBLICATION_SCOPE.md"
if approved_external:
    notice.write_text(
       "# Hays Botany - individually reviewed photo pilot\n\n"
       f"This public family site has **{len(cards)} existing species text lessons** and "
       f"**{len(approved_external)} externally hosted, individually credited CC BY photo(s)** "
       "referenced through the reviewed external photo manifest.\n\n"
       "No source photograph bytes or unverified media are copied to the Pages site. "
       "Approved links point directly to Wikimedia Commons, and the card shows photographer, "
       "license, and original source page. Each approved image was already included in "
       "the historical species source record. This does not establish photo/anatomy completeness.\n\n"
       "Remaining historical photos are withheld for individual rights and identity review. "
       "The original learner remains a photo fallback.\n",encoding="utf-8")
else:
    notice.write_text("# Hays Botany family text-only learner preview\n\n"
      f"This public learner currently contains **{len(cards)} existing species teaching summaries** "
      "from the migrated family source cards. **No third-party image files or remote embedded photos** "
      "are included in the output. Historical source-photo records and credits are preserved "
      "unchanged on the staging branch for an individual rights review before gallery use.\n\n"
      "Source repository being public does not establish rights to distribute all original photographs. "
      "Photographs can be added to the WEBSITE only when individually verified for display, "
      "attribution, license and adaptation rights. The old public learner remains the "
      "fallback for existing verified photographs and full lessons.\n",encoding="utf-8")
report={"status":"PASS_EXISTING_TEXT_DATA_ONLY","collection":CONFIG["collection_id"],
 "source_species":len(cards),"published_site_species":len(cards),
 "distinct_families":len(counts),"external_photos_downloaded":0,
 "embedded_original_photo_files":0,"private_photo_quarantine_files_copied":0,
 "photo_claimed_publicly_permitted_without_review":0,
 "existing_public_cc_photo_links":len(approved_external),
 "family_pages_ready_for_text_browsing":True,"original_hub_modified":False,
 "source_family_branch_modified":False,"new_plant_installations":0}
(DEST/"site-build-text-only-report.json").write_text(json.dumps(report,indent=2)+"\n")
print("HAYS_SAFE_TEXT_SITE_BUILD_PASS",json.dumps(report,sort_keys=True))
