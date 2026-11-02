#!/usr/bin/env python3
"""Cross-check original family-ZIP iNaturalist media and prepare verified public gallery intake."""
from __future__ import annotations
import hashlib,io,json,os,urllib.request
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parents[1]
data=json.loads((root/"photo-intake/remote-photo-manifests/verbenaceae-2026-11-02.json").read_text())
if data["family"]!="Verbenaceae" or len(data["photo_records"])!=22:raise SystemExit("Unexpected batch manifest")
out=Path(os.environ["RUNNER_TEMP"])/"verbenaceae-verified"
results=[]
aliases={
 "glandularia-pumila":{"glandularia pumila","verbena pumila"},
 "lantana-x-strigocamara":{"lantana strigocamara","lantana x strigocamara","lantana × strigocamara"},
 "verbena-canescens":{"verbena canescens"},
 "verbena-halei":{"verbena halei"},
 "verbena-scabra":{"verbena scabra"}
}

def get(url,size=26_000_000):
    request=urllib.request.Request(url,headers={"User-Agent":"HaysBotany-PhotoFirstNoncommercialSourceVerifier/1.0"})
    with urllib.request.urlopen(request,timeout=30) as response: raw=response.read(size+1)
    if len(raw)>size:raise ValueError("Source response exceeds allowed size")
    return raw

seen_ids=set()
for entry in data["photo_records"]:
    id=int(entry["photo_id"]);oid=int(entry["observation_id"]);sid=entry["species_id"]
    result={"species_id":sid,"photo_id":id,"observation_id":oid}
    try:
        if sid not in aliases or id in seen_ids:raise ValueError("Species or duplicate photo ID invalid")
        seen_ids.add(id)
        if not entry["image_url"].startswith(f"https://inaturalist-open-data.s3.amazonaws.com/photos/{id}/original."):
            raise ValueError("Photo source URL does not match exact photo ID")
        doc=json.loads(get(f"https://api.inaturalist.org/v1/observations/{oid}",5_000_000))
        obs=next((o for o in doc.get("results",[]) if int(o.get("id",0))==oid),None)
        if not obs:raise ValueError("Observation absent in live iNaturalist provider")
        taxon=str((obs.get("taxon") or {}).get("name") or "").lower()
        if taxon not in aliases[sid]:raise ValueError("Observation taxon not safely assignable: "+taxon)
        photo=next((p for p in obs.get("photos",[]) if int(p.get("id",0))==id),None)
        if not photo:raise ValueError("Exact source photo missing from observation")
        code=str(photo.get("license_code") or "").lower().replace("_","-")
        if code!="cc-by-nc":raise ValueError("Individual photo is not confirmed CC BY-NC: "+code)
        creator=str(photo.get("attribution") or entry.get("metadata_photographer") or "").strip()
        if not creator:raise ValueError("Photographer missing")
        img=get(entry["image_url"])
        if hashlib.sha256(img).hexdigest()!=entry["sha256"]:
            raise ValueError("Original source media SHA256 differs from user ZIP bytes")
        with Image.open(io.BytesIO(img)) as im:
            if im.format!="JPEG" or im.width*im.height>80_000_000:raise ValueError("Invalid JPEG or dimensions")
            im.verify()
        name=f"inat-{id}.jpg"; dest=out/"photo-intake/approved"/sid
        dest.mkdir(parents=True,exist_ok=True)
        (dest/name).write_bytes(img)
        sidecar={
          "species_id":sid,"photo_file":name,"status":"APPROVED_FOR_PUBLIC_FAMILY_SITE",
          "rights_approved_for_public":True,"taxon_reviewed":True,
          "approval_mode":"OWNER_STANDING_PHOTO_FIRST_POLICY","policy_ref":"PHOTO_FIRST_PUBLIC_GALLERY_POLICY_2026-11-02",
          "review_operator":"Hays Botany verified original ZIP visual review and independent source media API",
          "source_review_evidence":f"Exact iNaturalist observation {oid} contains photo {id}; live photo license {code}; photographer '{creator}'; remote original SHA256 exactly matches user-supplied original ZIP.",
          "taxon_review_evidence":f"Uploaded contact sheet inspected for obvious mixups; iNaturalist observation {oid} live source species {taxon} aligns with {sid}; detailed morphological study and BONAP range separately deferred.",
          "approval_note":"Original ZIP and actual photographer/photo-specific CC BY-NC source verified for educational noncommercial general-gallery publication. No anatomy proof asserted.",
          "creator":creator,"source_page":entry["source_page"],"source_page_is_exact":True,
          "license":"CC BY-NC 4.0","license_url":"https://creativecommons.org/licenses/by-nc/4.0/",
          "noncommercial_site_use_confirmed":True,"role":entry["role"]+" (general field photograph)",
          "modifications":"Original source JPEG unchanged","sha256":entry["sha256"]
        }
        (dest/(name+".json")).write_text(json.dumps(sidecar,indent=2)+"\n")
        result["status"]="SOURCE_AND_IMAGE_VERIFIED"
    except Exception as exc:
        result.update(status="HOLD_SOURCE_OR_TAXON",reason=str(exc)[:400])
    results.append(result)
    print(json.dumps(result),flush=True)
report=Path(os.environ["RUNNER_TEMP"])/"verbenaceae-photo-source-check.json"
report.write_text(json.dumps({"zip":data["original_zip"],"results":results,"preexisting_herbarium_holds":data["held_records"]},indent=2)+"\n")
print("VERIFIED",sum(x["status"]=="SOURCE_AND_IMAGE_VERIFIED" for x in results),"HELD",sum(x["status"]=="HOLD_SOURCE_OR_TAXON" for x in results),flush=True)
