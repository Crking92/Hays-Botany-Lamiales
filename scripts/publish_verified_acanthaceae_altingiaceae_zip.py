#!/usr/bin/env python3
"""Photo-first source-verified original ZIP image backfill. No unverified media is published."""
from __future__ import annotations
import argparse,base64,hashlib,io,json,os,re,struct,time,urllib.request,zlib
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
 "justicia-americana":{"dianthera americana"}, # Kew homotypic synonym https://powo.science.kew.org/taxon/78915-2
 "aquarius-cordifolius":{"echinodorus cordifolius"}, # Kew homotypic synonym https://powo.science.kew.org/taxon/77182733-1
 "anisacanthus-quadrifidus-var-wrightii":{"anisacanthus quadrifidus wrightii"}, # Identical 3-term rank-omitted variety label; Kew https://powo.science.kew.org/taxon/952518-1
 "hygrophila-costata":{"hygrophila lacustris"}, # Kew accepted synonym https://powo.science.kew.org/taxon/49712-1
 "ruellia-ciliatiflora":{"ruellia nudiflora","ruellia occidentalis"}, # Kew accepted synonyms https://powo.science.kew.org/taxon/53920-1
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
        if sidindex>=len(m["species"]) or ext not in (0,1,2,3):raise ValueError("Bad source record")
        yield m["species"][sidindex],pid,oid,hash_bytes.hex(),({0:"jpg",1:"jpeg",2:"png",3:"JPG"}[ext])
def matches(expected,taxon):
    norm=lambda n: re.sub(r"[^a-z0-9]+"," ",str(n).lower().replace("×","x")).strip()
    target=norm(expected); name=norm(taxon)
    species_level=len(target.split())==2
    return name==target or (species_level and (name.startswith(target+" subsp ") or name.startswith(target+" var "))) or name in {norm(v) for v in SYNONYMS.get(expected,set())}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--wave",type=int,required=True,choices=(1,2))
    parser.add_argument("--source-root",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    wrapper=json.loads(args.manifest.read_text())
    if wrapper.get("encoding")=="zlib+base64-json":
        m=json.loads(zlib.decompress(base64.b64decode(wrapper["payload_b64"],validate=True)))
    else:
        m=wrapper
    if wrapper.get("batch_id")!=m.get("batch_id") or wrapper.get("zip_sha256")!=m.get("zip_sha256") or wrapper.get("repository")!=m.get("repository"):raise SystemExit("Manifest wrapper identity mismatch")
    source=json.loads(Path("site/data/collection-index.json").read_text())
    site_meta=json.loads(Path("site/data/collection-meta.json").read_text())
    cards={x["id"]:x for x in source["entries"]}
    if m["batch_id"]!="acanthaceae-through-altingiaceae-2026-11-04":raise SystemExit("Unexpected batch")
    if m["repository"]!=site_meta.get("repository_full_name"):raise SystemExit("Manifest routed to incorrect family website")
    if m["original_images"]!=m["image_hashes_validated"] or m["internal_duplicates"]!=0:raise SystemExit("Uploaded ZIP integrity not confirmed")
    if len(m["species"])!=len(set(m["species"])):raise SystemExit("Duplicate species in manifest")
    if len(m["zip_sha256"])!=64:raise SystemExit("Bad ZIP identity")
    if any(not matches(sid,m.get("source_taxa",{}).get(sid,"")) for sid in m["species"]):
        raise SystemExit("Original ZIP species name mismatch with indexed family species")
    current_sources={}; current_shas={}; source_hashes={}
    for sid in m["species"]:
        if sid not in cards or cards[sid]["family"] not in site_meta["family_assignments"]:
            raise SystemExit("Target species not in the assigned family repository: "+sid)
    def remember(sid,photo):
        url=photo.get("source_page")
        sha=photo.get("sha256")
        if url:
            if url in current_sources and current_sources[url]!=sid: raise SystemExit("Existing source in different species")
            current_sources[url]=sid
            if sha:source_hashes[url]=sha
        if sha:
            if sha in current_shas and current_shas[sha]!=sid: raise SystemExit("Existing SHA256 in different species")
            current_shas[sha]=sid
    for path in Path("site/data/species").glob("*.json"):
        card=json.loads(path.read_text())
        for photo in card.get("verified_photos",[]): remember(card["id"],photo)
    public=Path("site/data/reviewed-external-photo-manifest.json")
    if public.is_file():
        entries=json.loads(public.read_text()).get("species",{})
        for csid,photos in entries.items():
            for photo in photos: remember(csid,photo)
    report=[];seen=set()
    records=list(decode(m))
    if len(records)!=m["photos_for_source_checks"]:raise SystemExit("Original photo inventory mismatch")
    if m["original_images"]!=len(records)+len(m["offline_held_media"]):raise SystemExit("Institutional hold inventory does not reconcile")
    for sid,pid,oid,sha,ext in records[(args.wave-1)*40:args.wave*40]:
        row={"species_id":sid,"photo_id":pid,"observation_id":oid}
        try:
            if (sid,pid) in seen:raise ValueError("Duplicate original photo ID")
            seen.add((sid,pid))
            src=f"https://www.inaturalist.org/photos/{pid}"
            if src in current_sources or sha in current_shas:
                prior=current_sources.get(src,current_shas.get(sha))
                if prior!=sid:raise ValueError("Exact source/hash already on another species: "+str(prior))
                if src in source_hashes and source_hashes[src]!=sha:raise ValueError("Source ID matches but SHA256 differs")
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
            attribution_origin="live iNaturalist API"
            if not attribution or attribution.lower() in {"no rights reserved","some rights reserved"}:
                original_credit=m.get("source_metadata_credits",{}).get(str(pid))
                attribution=str((original_credit.get("name") if isinstance(original_credit,dict) else original_credit) or "").strip()
                attribution_origin="original user ZIP credit record"
                if not attribution:raise ValueError("Neither live provider nor original ZIP establishes creator credit")
            if len(attribution)>400:raise ValueError("Unreasonable credit length")
            url=f"https://inaturalist-open-data.s3.amazonaws.com/photos/{pid}/original.{ext}"
            img=grab(url,25*1024*1024)
            if hashlib.sha256(img).hexdigest()!=sha:raise ValueError("Exact source original SHA256 differs from supplied ZIP")
            with Image.open(io.BytesIO(img)) as image:
                if image.format!=("PNG" if ext=="png" else "JPEG") or image.width*image.height>80_000_000:raise ValueError("Invalid original photo")
                image.verify()
            filename=f"inat-{pid}.{ext.lower()}"
            folder=args.source_root/"photo-intake/approved"/sid
            folder.mkdir(parents=True,exist_ok=True)
            (folder/filename).write_bytes(img)
            sidecar={
               "species_id":sid,"photo_file":filename,
               "status":"APPROVED_FOR_PUBLIC_FAMILY_SITE",
               "rights_approved_for_public":True,"taxon_reviewed":True,
               "approval_mode":"OWNER_STANDING_PHOTO_FIRST_POLICY",
               "policy_ref":"PHOTO_FIRST_PUBLIC_GALLERY_POLICY_2026-11-02",
               "review_operator":"Hays Botany Acanthaceae–Altingiaceae original ZIP source verifier",
               "source_review_evidence":f"Live iNaturalist observation {oid}, photo {pid}, individual license {code}, exact source photo URL. Source media SHA256 matches supplied original ZIP: {sha}. Credit evidence: {attribution_origin}.",
               "taxon_review_evidence":f"Four original ZIP contact sheets reviewed for basic botanical identity and useful whole-plant and morphology coverage. Live source name {name} maps to indexed species {sid} (Kew-backed synonym if necessary); specialist morphology and BONAP range deferred.",
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
                    "library_backup":"NONE__OWNER_KEEP_ORIGINAL_IN_LAPTOP_ARCHIVED_FOLDER","offline_held_media":m["offline_held_media"],"results":report},indent=2)+"\n")
    counts={s:sum(x["status"]==s for x in report) for s in ("ORIGINAL_AND_RIGHTS_VERIFIED","ALREADY_PUBLISHED","HELD")}
    print("PHOTO_FIRST_MULTIFAMILY_SOURCE_RESULTS",json.dumps(counts),flush=True)
if __name__=="__main__":main()
