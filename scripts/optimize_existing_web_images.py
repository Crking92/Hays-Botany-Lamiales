#!/usr/bin/env python3
"""Create small public Lamiales JPEGs without deleting source photo provenance.

The exact pre-optimization live originals remain pinned to an archive branch.
Run only from a clean GitHub Actions checkout with --archive-commit set.
"""
import argparse,hashlib,io,json,subprocess
from pathlib import Path
from PIL import Image,ImageOps

MAX_BYTES=760*1024
MAX_SITE_BYTES=750_000_000

def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def archive_paths(commit):
    lines=subprocess.check_output(["git","ls-tree","-r",commit,"--","site/media"],text=True).splitlines()
    return {path:line.split()[2] for line in lines if "\t" in line for path in [line.split("\t",1)[1]]}

def resize(source):
    with Image.open(io.BytesIO(source)) as original:
        original.load()
        img=ImageOps.exif_transpose(original)
        if img.mode!="RGB":
            img=img.convert("RGB")
        profile=original.info.get("icc_profile")
        if profile and len(profile)>131072:
            profile=None
        best=None
        for edge,quality in ((2600,85),(2400,83),(2200,81),(2000,80),
                             (1850,78),(1700,76),(1600,74),(1450,72),(1250,70)):
            sample=img.copy()
            sample.thumbnail((edge,edge),Image.Resampling.LANCZOS)
            out=io.BytesIO()
            sample.save(out,format="JPEG",quality=quality,progressive=True,
                        optimize=True,subsampling=0,icc_profile=profile)
            data=out.getvalue()
            if best is None or len(data)<len(best):
                best=data
            if len(data)<=MAX_BYTES:
                return data
        if best and len(best)<=MAX_BYTES:
            return best
        raise ValueError("DISPLAY_SIZE_HOLD: could not preserve a usable JPEG under budget")

def main():
    pa=argparse.ArgumentParser()
    pa.add_argument("--archive-commit",required=True)
    pa.add_argument("--site",default="site")
    pa.add_argument("--archive-branch",required=True)
    a=pa.parse_args()
    site=Path(a.site)
    gallery=json.loads((site/"data/gallery-index.json").read_text())
    catalog=json.loads((site/"data/collection-index.json").read_text())
    assert len(catalog["entries"])==gallery["species"]
    assert set(gallery["entries"])=={row["id"] for row in catalog["entries"]}
    manifest_path=site/"data/reviewed-external-photo-manifest.json"
    manifest=json.loads(manifest_path.read_text())
    manifest_photos={p["src"]:p for plist in manifest["species"].values() for p in plist if p.get("src","").startswith("media/")}
    manifest_modified=False
    originals=archive_paths(a.archive_commit)
    total_original_bytes=0
    total_display_bytes=0
    optimized=0
    same=0
    refs=set()
    changes=[]
    for entry in catalog["entries"]:
        sid=entry["id"]
        cardpath=site/"data/species"/(sid+".json")
        card=json.loads(cardpath.read_text())
        photos=card["verified_photos"]
        assert len(photos)==entry["photo_count"]==gallery["entries"][sid]["count"]
        edited=False
        for photo in photos:
            src=photo["src"]
            assert src.startswith("media/"+sid+"/") and src not in refs,src
            refs.add(src)
            local=site/src
            assert local.is_file() and not local.is_symlink(),src
            raw=local.read_bytes()
            total_original_bytes+=len(raw)
            archivepath="site/"+src
            assert archivepath in originals,src
            assert originals[archivepath]==blob(raw),("Archive does not match public original",src)
            if photo.get("sha256"):
                assert hashlib.sha256(raw).hexdigest()==photo["sha256"],src
            assert photo.get("source_blob_sha")==blob(raw),src
            if local.suffix.lower() not in (".jpg",".jpeg") or len(raw)<=MAX_BYTES:
                total_display_bytes+=len(raw)
                same+=1
                continue
            display=resize(raw)
            assert len(display)<len(raw) and len(display)<=MAX_BYTES,src
            local.write_bytes(display)
            photo["display_sha256"]=hashlib.sha256(display).hexdigest()
            photo["display_blob_sha"]=blob(display)
            photo["display_original_site_sha256"]=hashlib.sha256(raw).hexdigest()
            photo["display_original_archive_commit"]=a.archive_commit
            photo["display_modifications"]="Resized and JPEG-compressed for website display; original photo preserved in pinned family archive"
            photo["modified"]="Resized and recompressed web display copy; source note: "+(photo.get("modified") or "No prior modification note")
            if src in manifest_photos:
                mp=manifest_photos[src]
                assert (mp.get("creator"),mp.get("license"),mp.get("source_page"),mp.get("source_blob_sha"))==(photo.get("creator"),photo.get("license"),photo.get("source_page"),photo.get("source_blob_sha")),src
                for field in ("display_sha256","display_blob_sha","display_original_site_sha256","display_original_archive_commit","display_modifications","modified"):
                    mp[field]=photo[field]
                manifest_modified=True
            edited=True
            optimized+=1
            total_display_bytes+=len(display)
            changes.append({"src":src,"original_bytes":len(raw),"display_bytes":len(display),
                            "original_sha256":hashlib.sha256(raw).hexdigest(),
                            "display_sha256":photo["display_sha256"]})
        if edited:
            cardpath.write_text(json.dumps(card,indent=2,ensure_ascii=False)+"\n")
    actual={p.relative_to(site).as_posix() for p in (site/"media").rglob("*") if p.is_file()}
    assert refs==actual,{"orphan":list(actual-refs)[:8],"missing":list(refs-actual)[:8]}
    assert len(refs)==gallery["photo_count"]
    if manifest_modified:
        manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\\n".replace("\\n","\n"))
    sitebytes=sum(p.stat().st_size for p in site.rglob("*") if p.is_file())
    assert sitebytes<=MAX_SITE_BYTES,("SITE_BYTES_OVER_TARGET",sitebytes)
    report={"family_repository":"Crking92/Hays-Botany-Lamiales",
            "archive_branch":a.archive_branch,"archive_commit":a.archive_commit,
            "photo_count":len(refs),"optimized":optimized,"unchanged":same,
            "media_before_bytes":total_original_bytes,"media_after_bytes":total_display_bytes,
            "saved_bytes":total_original_bytes-total_display_bytes,"site_bytes":sitebytes,
            "photo_changes":changes}
    (site/"data/web-display-optimization.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print("FAMILY_WEB_IMAGE_OPTIMIZATION_PASS "+json.dumps({k:v for k,v in report.items() if k!="photo_changes"}),flush=True)

if __name__=="__main__":
    main()
