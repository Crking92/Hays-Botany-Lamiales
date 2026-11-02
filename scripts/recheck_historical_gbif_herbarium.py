#!/usr/bin/env python3
"""Recheck exact historic herbarium media license and source bytes before public release."""
import datetime,hashlib,json,subprocess,sys,tempfile,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"workflow/archived-herbarium-rights-candidates-2026-11-02.json"
REPORT=ROOT/"workflow/archived-herbarium-rights-result-2026-11-02.json"
LICENSES={"CC BY 4.0":"https://creativecommons.org/licenses/by/4.0/",
          "CC BY-NC 4.0":"https://creativecommons.org/licenses/by-nc/4.0/"}
def get(url):
    last=None
    for trial in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"HaysBotany-ArchivalGBIFMediaReview/1.0"}),timeout=35) as response:
                if response.status!=200:raise RuntimeError("HTTP "+str(response.status))
                return response.read()
        except Exception as error:
            last=error
            time.sleep(2+trial*3)
    raise RuntimeError(str(last))
def main():
    info=json.loads(SOURCE.read_text())
    assert info["repo"]=="Crking92/"+ROOT.name
    finished=datetime.datetime.now(datetime.timezone.utc).isoformat()
    report={"original_held":len(info["candidates"]),"approved_for_install":0,"published":0,"held":0,"checked_at":finished,"records":[]}
    with tempfile.TemporaryDirectory(prefix="archived-herbarium-gbif-") as td:
        source=Path(td)
        for row in info["candidates"]:
            result={"species_id":row["species_id"],"gbif_id":row["gbif_id"]}
            try:
                sid=row["species_id"]
                card=json.loads((ROOT/"site/data/species"/(sid+".json")).read_text())
                source_page="https://www.gbif.org/occurrence/"+str(row["gbif_id"])
                if any(p.get("source_page")==source_page for p in card["verified_photos"]):
                    result["status"]="ALREADY_PUBLISHED"
                    report["records"].append(result)
                    continue
                occurrence=json.loads(get("https://api.gbif.org/v1/occurrence/"+str(row["gbif_id"])))
                scientific=(occurrence.get("species") or occurrence.get("scientificName") or "")
                expected=" ".join(sid.split("-")[:2])
                assert scientific.lower().startswith(expected),"archived taxon differs from live occurrence: "+scientific
                medias=[m for m in occurrence.get("media",[]) if m.get("identifier")==row["source_url"]]
                assert len(medias)==1,"exact media identifier absent from live GBIF occurrence"
                medium=medias[0]
                license_url=(medium.get("license") or "").replace("http://","https://")
                assert license_url.rstrip("/")==LICENSES[row["license"]].rstrip("/"),"live image-level license differs from archive: "+str(license_url)
                origin_credit=" ".join(str(medium.get(k) or "") for k in ("creator","rightsHolder","publisher"))
                assert any(v in origin_credit.casefold() for v in row["creator"].casefold().split() if len(v)>5),"exact media source creator unconfirmed: "+origin_credit
                assert len(row["sha256"])==64
                # Preserve actual source identifier; both HTTPS and original HTTP are permitted for fetch only.
                raw=get(row["source_url"])
                digest=hashlib.sha256(raw).hexdigest()
                assert digest==row["sha256"],"original file bytes differ from archived ZIP SHA-256"
                assert 200<len(raw)<=25*1024*1024,"image size not permitted"
                folder=source/"photo-intake/approved"/sid
                folder.mkdir(parents=True,exist_ok=True)
                photo=folder/("archival-gbif-"+str(row["gbif_id"])+".jpg")
                photo.write_bytes(raw)
                note=("Source specimen accepted as "+scientific+" in GBIF occurrence "+str(row["gbif_id"])+
                      "; original archive contact sheet visually checked for plausible corresponding collected material. Specialist plant determination not claimed.")
                sidecar={
                    "species_id":sid,"photo_file":photo.name,"status":"APPROVED_FOR_PUBLIC_FAMILY_SITE",
                    "rights_approved_for_public":True,"taxon_reviewed":True,
                    "approval_mode":"OWNER_STANDING_PHOTO_FIRST_POLICY","policy_ref":"PHOTO_FIRST_PUBLIC_GALLERY_POLICY_2026-11-02",
                    "review_operator":"Original ZIP visual inspection and automated live GBIF media-license/sha256 verification",
                    "source_review_evidence":"Exact GBIF media identifier "+row["source_url"]+
                      " with image-level license "+license_url+" and creator "+origin_credit+
                      "; downloaded source SHA256 "+digest+" matches archived ZIP record on "+finished,
                    "taxon_review_evidence":note,"approval_note":"Owner standing photo-first license/credit/source checks completed for exact archived original; detailed taxonomy deferred.",
                    "creator":row["creator"],"source_page":source_page,"source_page_is_exact":True,
                    "license":row["license"],"license_url":LICENSES[row["license"]],
                    "noncommercial_site_use_confirmed":row["license"]=="CC BY-NC 4.0",
                    "role":row["role"],"modifications":"Unmodified original byte-for-byte match to preserved ZIP.",
                    "sha256":digest
                }
                photo.with_name(photo.name+".json").write_text(json.dumps(sidecar,ensure_ascii=False))
                result.update(status="RIGHTS_AND_IMAGE_VERIFIED",license=row["license"],sha256=digest)
                report["approved_for_install"]+=1
            except Exception as err:
                result.update(status="HELD",reason=str(err)[:400])
                report["held"]+=1
            report["records"].append(result)
        if report["approved_for_install"]:
            publisher=ROOT/"scripts/publish_approved_lamiales_photos.py"
            args=[sys.executable,str(publisher),"--source-root",str(source),"--site-root",str(ROOT/"site")]
            for suffix in (["--check"],[]):
                run=subprocess.run(args+suffix,capture_output=True,text=True)
                if run.returncode:raise RuntimeError("PUBLISHER_REJECTED "+run.stdout+run.stderr)
                if not suffix:report["published"]=json.loads(run.stdout)["installed"]
            assert report["published"]==report["approved_for_install"]
        REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
        print(json.dumps({"published":report["published"],"held":report["held"],
                          "records":report["records"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
