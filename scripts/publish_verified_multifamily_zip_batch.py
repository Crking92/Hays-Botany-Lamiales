#!/usr/bin/env python3
"""Photo-first source-verified original ZIP image backfill. No unverified media is published."""
from __future__ import annotations
import argparse,base64,hashlib,io,json,os,re,struct,time,urllib.request
from pathlib import Path
from PIL import Image

LICENSES={
 "cc0":("CC0 1.0","https://creativecommons.org/publicdomain/zero/1.0/"),
 "cc-by":("CC BY 4.0","https://creativecommons.org/licenses/by/4.0/"),
 "cc-by-sa":("CC BY-SA 4.0","https://creativecommons.org/licenses/by-sa/4.0/"),
 "cc-by-nc":("CC BY-NC 4.0","https://creativecommons.org/licenses/by-nc/4.0/"),
 "cc-by-nc-sa":("CC BY-NC-SA 4.0","https://creativecommons.org/licenses/by-nc-sa/4.0/")
}
RECORD_SIZE=42
# Only names already checked as direct synonyms, not broader unidentified look-alikes.
SYNONYMS={
 "azolla-caroliniana":{"azolla cristata"},
 "smilax-tamnoides":{"smilax hispida"},
 "capsicum-annuum-var-aviculare":{"capsicum annuum var. glabriusculum"},
 "buddleja-racemosa":{"buddleja sessiliflora"},
 "talinum-aurantiacum":{"phemeranthus aurantiacus"},
}
def grab(url,maxsize):
    req=urllib.request.Request(url,headers={"User-Agent":"HaysBotanyEducationalPhotoFirst/1.0 (original-media license verification)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=30) as r:data=r.read(maxsize+1)
            if len(data)>maxsize:raise ValueError("Source media exceeds size limit")
            return data
        except Exception:
            if attempt==2:raise
            time.sleep(1+attempt)
def decode(m):
    data=base64.b64decode(m["records_base64"],validate=True)
    if len(data)%RECORD_SIZE:raise ValueError("Corrupt original photo record size")
    for sidindex,pid,oid,hash_bytes,ext in struct.iter_unpack(">BII32sB",data):
        if sidindex>=len(m["species"]) or ext not in (0,1):raise ValueError("Bad source record")
        yield m["species"][sidindex],pid,oid,hash_bytes.hex(),("jpeg" if ext else "jpg")
def matches(expected,taxon):
    target=expected.replace("-"," ")
    name=taxon.lower().replace("×","x").strip()
    return name==target or name.startswith(target+" subsp.") or name.startswith(target+" var.") or name in SYNONYMS.get(expected,set())
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--source-root",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    m=json.loads(args.manifest.read_text())
    source=json.loads(Path("site/data/collection-index.json").read_text())
    site_meta=json.loads(Path("site/data/collection-meta.json").read_text())
    cards={x["id"]:x for x in source["entries"]}
    if m["batch_id"]!="salicaceae-through-tamaricaceae-2026-11-02":raise SystemExit("Unexpected batch")
    if len(m["species"])!=len(set(m["species"])):raise SystemExit("Duplicate species in manifest")
    current=set()
    for sid in m["species"]:
        if sid not in cards:raise SystemExit("Target species not in this family repo: "+sid)
        card=json.loads((Path("site/data/species")/(sid+".json")).read_text())
        current.update((x.get("source_page"),x.get("sha256")) for x in card.get("verified_photos",[]))
    report=[];seen=set()
    records=list(decode(m))
    for sid,pid,oid,sha,ext in records:
        row={"species_id":sid,"photo_id":pid,"observation_id":oid}
        try:
            if (sid,pid) in seen:raise ValueError("Duplicate original photo ID")
            seen.add((sid,pid))
            src=f"https://www.inaturalist.org/photos/{pid}"
            if (src,sha) in current:
                row["status"]="ALREADY_PUBLISHED"
                report.append(row);continue
            obs_json=json.loads(grab(f"https://api.inaturalist.org/v1/observations/{oid}",5_000_000))
            obs=next((x for x in obs_json.get("results",[]) if int(x.get("id",-1))==oid),None)
            if obs is None:raise ValueError("Source observation not found")
            name=str((obs.get("taxon") or {}).get("name") or "")
            if not matches(sid,name):raise ValueError("Species name/synonym needs later review: "+name)
            photo=next((x for x in obs.get("photos",[]) if int(x.get("id",-1))==pid),None)
            if photo is None:raise ValueError("Individual photo not found on observation")
            code=str(photo.get("license_code") or "").lower().replace("_","-")
            if code not in LICENSES:raise ValueError("Unsupported/unknown individual source license: "+code)
            license_name,license_url=LICENSES[code]
            is_nc=code in {"cc-by-nc","cc-by-nc-sa"}
            if is_nc and site_meta.get("photo_license_policy",{}).get("noncommercial_educational_use") is not True:
                raise ValueError("Site has not explicitly enabled noncommercial-only images")
            attribution=str(photo.get("attribution") or "").strip()
            if not attribution or attribution.lower() in {"no rights reserved","some rights reserved"}:
                if code=="cc0":attribution="CC0 original contributor (see exact source)"
                else:raise ValueError("Photographer attribution not available from source")
            if len(attribution)>400:raise ValueError("Unreasonable credit length")
            url=f"https://inaturalist-open-data.s3.amazonaws.com/photos/{pid}/original.{ext}"
            img=grab(url,25*1024*1024)
            if hashlib.sha256(img).hexdigest()!=sha:raise ValueError("Exact source original SHA256 differs from supplied ZIP")
            with Image.open(io.BytesIO(img)) as image:
                if image.format!="JPEG" or image.width*image.height>80_000_000:raise ValueError("Invalid original photo")
                image.verify()
            filename=f"inat-{pid}.{ext}"
            folder=args.source_root/"photo-intake/approved"/sid
            folder.mkdir(parents=True,exist_ok=True)
            (folder/filename).write_bytes(img)
            sidecar={
               "species_id":sid,"photo_file":filename,
               "status":"APPROVED_FOR_PUBLIC_FAMILY_SITE",
               "rights_approved_for_public":True,"taxon_reviewed":True,
               "approval_mode":"OWNER_STANDING_PHOTO_FIRST_POLICY",
               "policy_ref":"PHOTO_FIRST_PUBLIC_GALLERY_POLICY_2026-11-02",
               "review_operator":"Hays Botany multi-family original ZIP contact-sheet/source verifier",
               "source_review_evidence":f"Live iNaturalist observation {oid}, photo {pid}, individual license {code}, exact source photo URL. Source media SHA256 matches supplied original ZIP: {sha}.",
               "taxon_review_evidence":f"Contact sheets checked for obvious wrong organism. Live source name {name} maps to indexed species {sid}; specialist morphology and BONAP range deferred.",
               "approval_note":"Owner standing photo-first authorization: original image, live photo-specific source reuse rights, and basic species assignment verified. Detailed plant anatomy deferred.",
               "creator":attribution,"source_page":src,"source_page_is_exact":True,
               "license":license_name,"license_url":license_url,
               "noncommercial_site_use_confirmed":True,
               "role":"General field photograph; exact structure and detailed botanical identification deferred",
               "modifications":"Original source photo, no edits",
               "sha256":sha
            }
            (folder/(filename+".json")).write_text(json.dumps(sidecar,indent=2)+"\n")
            row["status"]="ORIGINAL_AND_RIGHTS_VERIFIED"
            row["license"]=license_name
        except Exception as err:
            row.update(status="HELD",reason=str(err)[:450])
        print(json.dumps(row),flush=True)
        report.append(row)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps({"batch":m["batch_id"],"original_zip_sha256":m["zip_sha256"],
                    "library_backup":m["library_backup"],"results":report},indent=2)+"\n")
    counts={s:sum(x["status"]==s for x in report) for s in ("ORIGINAL_AND_RIGHTS_VERIFIED","ALREADY_PUBLISHED","HELD")}
    print("PHOTO_FIRST_MULTIFAMILY_SOURCE_RESULTS",json.dumps(counts),flush=True)
if __name__=="__main__":main()
