#!/usr/bin/env python3
"""Balsaminaceae-Bixaceae ZIP exact-image source verifier: only license- and taxon-cleared photos reach public site."""
import argparse,base64,hashlib,io,json,re,struct,time,urllib.request
from pathlib import Path
from PIL import Image

LICENSES={
 "cc0":("CC0 1.0","https://creativecommons.org/publicdomain/zero/1.0/"),
 "cc-by":("CC BY 4.0","https://creativecommons.org/licenses/by/4.0/"),
 "cc-by-sa":("CC BY-SA 4.0","https://creativecommons.org/licenses/by-sa/4.0/"),
 "cc-by-nc":("CC BY-NC 4.0","https://creativecommons.org/licenses/by-nc/4.0/"),
 "cc-by-nc-sa":("CC BY-NC-SA 4.0","https://creativecommons.org/licenses/by-nc-sa/4.0/")}
EXT={0:"jpg",1:"jpeg",2:"JPG",3:"png"}
FMT={"jpg":"JPEG","jpeg":"JPEG","JPG":"JPEG","png":"PNG"}
def grab(url,maximum):
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"HaysBotanyNoncommercialPhotoLearner/1.0 (photo-specific rights verification)"})
            with urllib.request.urlopen(req,timeout=35) as response:
                b=response.read(maximum+1)
            if len(b)>maximum:raise ValueError("Image/download exceeds limit")
            return b
        except Exception:
            if attempt==2:raise
            time.sleep(2+attempt)
def norm(s):
    return re.sub(r"[^a-z0-9]+"," ",str(s).lower().replace("×","x")).strip()
# No unreviewed taxonomic aliases are accepted by the verifier.
KEW_VERIFIED_SYNONYMS={}

def taxon_matches(sid,name):
    a=norm(sid);b=norm(name)
    rankless=lambda s:" ".join(w for w in s.split() if w not in {"var","subsp","ssp","subspecies"})
    return (a==b or rankless(a)==rankless(b)
            or (len(a.split())==2 and b.startswith(a+" "))
            or b in KEW_VERIFIED_SYNONYMS.get(sid,set()))
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",required=True,type=Path)
    parser.add_argument("--wave",required=True,type=int,choices=(1,2))
    parser.add_argument("--source-root",required=True,type=Path)
    parser.add_argument("--report",required=True,type=Path)
    args=parser.parse_args()
    wrapper=json.loads(args.manifest.read_text())
    if wrapper.get("encoding")!="zlib+base64-json":raise SystemExit("Unsupported source manifest")
    m=json.loads(__import__("zlib").decompress(base64.b64decode(wrapper["payload_b64"],validate=True)))
    if any(wrapper.get(k)!=m.get(k) for k in ("batch","repository_full_name","zip_sha256","original_images")):
        raise SystemExit("ZIP manifest identity mismatches source")
    if m.get("batch")!="balsaminaceae-through-bixaceae-2026-11-03":
        raise SystemExit("Unexpected source ZIP batch")
    if len(m["zip_sha256"])!=64 or m["original_images"]!=m["verified_local_checksums"] or m["exact_internal_duplicates"]!=0:
        raise SystemExit("Unverified original ZIP source integrity")
    raw=base64.b64decode(m["records_base64"],validate=True)
    if len(raw)%42:raise SystemExit("Corrupt original photo records")
    all_records=list(struct.iter_unpack(">BII32sB",raw))
    if len(all_records)+len(m["holds"])!=m["original_images"]:
        raise SystemExit("Photo source and held-photo inventory mismatch")
    if len(m["species"])!=len(set(m["species"])):raise SystemExit("Duplicate manifest species")
    site_meta=json.loads(Path("site/data/collection-meta.json").read_text())
    if site_meta.get("repository_full_name")!=m["repository_full_name"]:
        raise SystemExit("Wrong family-owned destination repository")
    if any(x.get("license_claim") is None for x in m["holds"]):
        raise SystemExit("Institutional image hold record missing original rights claim")
    cards={x["id"]:x for x in json.loads(Path("site/data/collection-index.json").read_text())["entries"]}
    seen_ids=set()
    for si,pid,oid,sha,ext in all_records:
        if si>=len(m["species"]) or ext not in EXT:raise SystemExit("Corrupt source record")
        if m["species"][si] not in cards or cards[m["species"][si]]["family"] not in site_meta["family_assignments"]:raise SystemExit("Species not on assigned site")
        if pid in seen_ids:raise SystemExit("Same exact photo ID assigned twice")
        seen_ids.add(pid)
    all_current_ids=set()
    all_current_hashes=set()
    for p in Path("site/data/species").glob("*.json"):
        for x in json.loads(p.read_text()).get("verified_photos",[]):
            if x.get("sha256"):all_current_hashes.add(x["sha256"])
            match=re.search(r"/photos/(\d+)",str(x.get("source_page","")))
            if match:all_current_ids.add(int(match.group(1)))
    # Each family route has at most 23 source candidates; publish one coherent batch.
    records=all_records
    results=[]
    for si,pid,oid,sha_bytes,extnum in records:
        sid=m["species"][si]
        sha=sha_bytes.hex()
        row={"species_id":sid,"photo_id":pid,"observation_id":oid}
        try:
            if pid==637037730:
                raise ValueError("Quality hold: photo shows a digital screen rather than a useful direct field view")
            if pid in all_current_ids or sha in all_current_hashes:
                row["status"]="ALREADY_PUBLISHED"
                results.append(row);continue
            obs_data=json.loads(grab("https://api.inaturalist.org/v1/observations/"+str(oid),5_000_000))
            obs=next((v for v in obs_data.get("results",[]) if int(v.get("id",-1))==oid),None)
            if obs is None:raise ValueError("Original iNaturalist observation missing")
            actual=str((obs.get("taxon") or {}).get("name") or "")
            if not taxon_matches(sid,actual):raise ValueError("Live source taxon mismatch or unresolved synonym: "+actual)
            photo=next((v for v in obs.get("photos",[]) if int(v.get("id",-1))==pid),None)
            if photo is None:raise ValueError("Exact original photo absent from observation")
            code=str(photo.get("license_code") or "").lower().replace("_","-")
            if code not in LICENSES:raise ValueError("Exact-photo license unsupported or revoked: "+code)
            license_name,license_url=LICENSES[code]
            is_nc=code in {"cc-by-nc","cc-by-nc-sa"}
            if is_nc and site_meta.get("photo_license_policy",{}).get("noncommercial_educational_use") is not True:
                raise ValueError("Noncommercial use not authorized at destination site")
            creator=str(photo.get("attribution") or "").strip()
            creator_source="live exact-photo attribution"
            if not creator or creator.lower() in {"some rights reserved","no rights reserved"}:
                # Exact SHA/ID matches user ZIP original, which includes source photo credit.
                credit=m.get("source_metadata_credits",{}).get(str(pid),{})
                creator=str((credit.get("name") if isinstance(credit,dict) else credit) or "").strip()
                creator_source="original ZIP's exact-photo photographer credit"
                if not creator:raise ValueError("Exact-photo photographer attribution not established")
            if len(creator)>400:raise ValueError("Photo attribution unexpectedly long")
            ext=EXT[extnum]
            source_url="https://inaturalist-open-data.s3.amazonaws.com/photos/%s/original.%s"%(pid,ext)
            original=grab(source_url,25*1024*1024)
            if hashlib.sha256(original).hexdigest()!=sha:raise ValueError("Live original differs from user ZIP SHA256")
            with Image.open(io.BytesIO(original)) as im:
                if im.format!=FMT[ext] or im.width*im.height>80_000_000:raise ValueError("Image format invalid")
                im.verify()
            dest=args.source_root/"photo-intake/approved"/sid
            dest.mkdir(parents=True,exist_ok=True)
            filename="inat-%s.%s"%(pid,ext.lower())
            (dest/filename).write_bytes(original)
            credit={
                "species_id":sid,"photo_file":filename,"status":"APPROVED_FOR_PUBLIC_FAMILY_SITE",
                "rights_approved_for_public":True,"taxon_reviewed":True,
                "approval_mode":"OWNER_STANDING_PHOTO_FIRST_POLICY",
                "policy_ref":"PHOTO_FIRST_PUBLIC_GALLERY_POLICY_2026-11-02",
                "review_operator":"Hays Botany family ZIP exact-original source verifier",
                "source_review_evidence":"Exact iNaturalist observation %s and photo %s checked individually for current %s rights, creator from %s, and identical SHA256 %s; source photograph %s."%(oid,pid,code,creator_source,sha,source_url),
                "taxon_review_evidence":"Original ZIP contact sheets visually screened for field identification and useful whole-plant, foliage, flowers and fruit, with uncertain morphology held. Live source taxon '%s' matches this assigned family species card %s. Specialist morphology/field characters deferred."%(actual,sid),
                "approval_note":"Original image from user ZIP independently matched against current licensed original source bytes, iNaturalist individual-photo reuse rights and basic taxon identity; detailed anatomy deferred.",
                "creator":creator,"source_page":"https://www.inaturalist.org/photos/"+str(pid),
                "source_page_is_exact":True,"license":license_name,"license_url":license_url,
                "noncommercial_site_use_confirmed":True,"role":"General field photograph, no anatomy claims",
                "modifications":"Original source photo; unaltered",
                "sha256":sha}
            (dest/(filename+".json")).write_text(json.dumps(credit,indent=2)+"\n")
            row["status"]="ORIGINAL_AND_RIGHTS_VERIFIED"
            row["license"]=license_name
        except Exception as e:
            row["status"]="HELD"
            row["reason"]=str(e)[:400]
        results.append(row)
        print(json.dumps(row),flush=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps({"batch":m["batch"],"wave":args.wave,
        "original_zip_sha256":m["zip_sha256"],"offline_held_rows":m["holds"],
        "results":results},indent=2)+"\n")
    print("FAMILY_ZIP_SOURCE_AUDIT",json.dumps({v:sum(r["status"]==v for r in results) for v in ("ORIGINAL_AND_RIGHTS_VERIFIED","ALREADY_PUBLISHED","HELD")}),flush=True)
if __name__=="__main__":main()
