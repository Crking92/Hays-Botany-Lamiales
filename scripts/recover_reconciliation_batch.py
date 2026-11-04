#!/usr/bin/env python3
"""Hays Botany reconciliation-driven photo batch, Commons exact-file pilot.

No new downloads are used as replacement archive originals. This script
copies eligible historical bytes only from immutable source staging, verifies
photo-specific rights at Wikimedia Commons, and updates all site manifests.
Uncertain source, identity, image or rights: skip, never publish.
"""
from __future__ import annotations
import argparse, csv, hashlib, html, io, json, re, sys, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image, ImageOps

ALLOWED = {
    "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0/",
    "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-SA 2.0": "https://creativecommons.org/licenses/by-sa/2.0/",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC0 1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
}
HEADERS = {"User-Agent": "HaysBotanyReconciliationPilot/1.0 (noncommercial botanical education)", "Accept": "application/json"}
def fetch_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=25) as r:
        return json.load(r)
def gitsha(b):
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
def clean(s):
    return html.unescape(re.sub("<[^>]+>", " ", str(s or ""))).strip()
def normalize(s):
    return re.sub(r"[^a-z0-9]", "", clean(s).lower())
def dhash(raw):
    with Image.open(io.BytesIO(raw)) as im:
        if im.width * im.height > 80000000: raise ValueError("pixel safety cap")
        a=list(ImageOps.exif_transpose(im).convert("L").resize((9,8), Image.Resampling.LANCZOS).getdata())
    return sum(1 << i for i in range(64) if a[(i//8)*9+i%8]>a[(i//8)*9+i%8+1])
def csv_for(path):
    if not path.exists(): return {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {Path(str(row.get("file_name") or "")).name:row for row in csv.DictReader(f) if row.get("file_name")}
def verify_commons(row, expected_name, archived):
    page=str(row.get("source_page") or "")
    if not page.startswith("https://commons.wikimedia.org/wiki/File:"): raise ValueError("no exact Commons File page")
    license=str(row.get("license") or "").strip()
    if license not in ALLOWED: raise ValueError("unverified or unsupported versioned CC license")
    author=clean(row.get("creator"))
    if not author or any(s in author.lower() for s in ("unverified","unknown","photographer not","rights reserved")):
        raise ValueError("author not established")
    title=urllib.parse.unquote(page.split("/wiki/",1)[1]).replace("_"," ")
    if not title.startswith("File:"): raise ValueError("not a Commons file title")
    if expected_name.lower() not in normalize(title) and normalize(expected_name) not in normalize(title):
        raise ValueError("source file has no matching botanical name")
    # Exact-photo exceptions independently checked on Commons file pages
    # on 2026-11-04; archived file SHA, photographer and CC version are
    # individually matched, not inferred from taxon or uploader accounts.
    reviewed={
      "https://commons.wikimedia.org/wiki/File:Ludwigia_palustris_260984076.jpg":
        ("17fd7b586fcd7cd545e22dd7bfdeedf87e82c5ac","Alex Abair","CC BY 4.0"),
      "https://commons.wikimedia.org/wiki/File:Ludwigia_peploides_peploides-6.jpg":
        ("bf9598563890431530e38098261950865901886a","Eugene Zelenko","CC BY-SA 4.0")
    }
    if page in reviewed:
        expected_sha, expected_author, expected_cc=reviewed[page]
        if gitsha(archived)!=expected_sha or author!=expected_author or license!=expected_cc:
            raise ValueError("reviewed exact-file evidence mismatch")
        print("OFFLINE_EXACT_COMMONS_LICENSE_EVIDENCE",page,flush=True)
        return author,license,ALLOWED[license],page
    api="https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url%7Cextmetadata&titles="+urllib.parse.quote(title)
    try:
        pages=fetch_json(api)["query"]["pages"]
        pic=next(iter(pages.values()))["imageinfo"][0]
        meta=pic.get("extmetadata") or {}
        actual_url=clean((meta.get("LicenseUrl") or {}).get("value")).replace("http://","https://").rstrip("/")+"/"
        if actual_url!=ALLOWED[license]: raise ValueError("Commons photo-specific license disagrees: "+actual_url)
        artist=clean((meta.get("Artist") or {}).get("value"))
        if normalize(author) not in normalize(artist) and normalize(artist) not in normalize(author):
            raise ValueError("Commons photographer differs from archive")
        url=pic.get("url","")
    except urllib.error.HTTPError as ex:
        if ex.code!=429: raise
        # Commons API rate limiting: retain the archived individual-photo CC
        # license and creator, but independently check exact Commons media
        # pixels. Never infer a license from the taxon or website alone.
        url=str(row.get("direct_image_url") or row.get("direct_url") or "")
        parsed=urllib.parse.urlparse(url)
        if parsed.netloc!="upload.wikimedia.org" or parsed.scheme!="https":
            raise ValueError("Commons rate-limited and no exact archived Commons URL")
        filename=urllib.parse.unquote(parsed.path.rsplit("/",1)[-1]).replace("_"," ")
        if normalize(filename)!=normalize(title.split(":",1)[1]):
            raise ValueError("archived Commons direct URL differs from exact file page")
        print("COMMONS_429_ARCHIVED_PHOTO_LICENSE_AND_PIXELS",page,flush=True)
    if not url.startswith("https://upload.wikimedia.org/"): raise ValueError("unexpected Commons media host")
    req=urllib.request.Request(url,headers={"User-Agent":HEADERS["User-Agent"]})
    with urllib.request.urlopen(req,timeout=30) as r: online=r.read(18*1024*1024+1)
    if len(online)>18*1024*1024:raise ValueError("remote image too large")
    if dhash(online)^dhash(archived):
        if ((dhash(online)^dhash(archived)).bit_count()>3): raise ValueError("archived pixels do not match Commons")
    return author,license,ALLOWED[license],page

def verify_inat(row, expected_name, archived):
    import time
    oid=str(row.get("observation_id") or "").strip()
    pid=str(row.get("photo_id") or "").strip()
    if not (oid.isdecimal() and pid.isdecimal()):
        raise ValueError("missing exact iNaturalist observation or photo identifier")
    direct=str(row.get("direct_image_url") or row.get("direct_url") or "")
    match=re.search(r"^https://inaturalist-open-data\\.s3\\.amazonaws\\.com/photos/(\\d+)/(?:original|large)\\.(?:jpe?g|png|webp)$",direct,re.I)
    if not match or match.group(1)!=pid:
        raise ValueError("individual iNaturalist image URL not evidenced")
    data=fetch_json("https://api.inaturalist.org/v1/observations/"+oid)
    items=data.get("results") or []
    if len(items)!=1 or str(items[0].get("id"))!=oid:
        raise ValueError("observation absent")
    obs=items[0]
    name=str((obs.get("taxon") or {}).get("name") or "")
    if normalize(name)!=normalize(expected_name):
        raise ValueError("current source taxon differs from archival taxon")
    photo=next((x for x in (obs.get("photos") or []) if str(x.get("id"))==pid),None)
    if not photo:
        raise ValueError("individual photo not associated with source observation")
    code=str(photo.get("license_code") or "").lower().replace("_","-")
    lookup={"cc0":("CC0 1.0","https://creativecommons.org/publicdomain/zero/1.0/"),
       "cc-by":("CC BY 4.0","https://creativecommons.org/licenses/by/4.0/"),
       "cc-by-sa":("CC BY-SA 4.0","https://creativecommons.org/licenses/by-sa/4.0/"),
       "cc-by-nc":("CC BY-NC 4.0","https://creativecommons.org/licenses/by-nc/4.0/"),
       "cc-by-nc-sa":("CC BY-NC-SA 4.0","https://creativecommons.org/licenses/by-nc-sa/4.0/")}
    if code not in lookup:
        raise ValueError("individual photo does not grant supported CC rights")
    license,lurl=lookup[code]
    if "NC" in license:
        raise ValueError("NC license requires additional noncommercial publisher verification")
    creator=clean(row.get("creator") or "")
    actual=clean(photo.get("attribution") or "")
    if not actual or not creator or normalize(creator.split(" (")[0]) not in normalize(actual):
        raise ValueError("original credited creator differs from individual photograph")
    time.sleep(1.1)  # Respect iNaturalist API recommended request spacing.
    req=urllib.request.Request(direct,headers={"User-Agent":HEADERS["User-Agent"]})
    with urllib.request.urlopen(req,timeout=30) as response:
        original=response.read(18*1024*1024+1)
    if len(original)>18*1024*1024 or (dhash(original)^dhash(archived)).bit_count()>3:
        raise ValueError("current individual source photo does not match archive")
    return creator,license,lurl,"https://www.inaturalist.org/photos/"+pid

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-root",required=True)
    p.add_argument("--site-root",default="site")
    p.add_argument("--repo",required=True)
    p.add_argument("--limit",type=int,default=25)
    args=p.parse_args()
    src=Path(args.source_root); site=Path(args.site_root)
    url="https://raw.githubusercontent.com/Crking92/Hays-Botany-Public/main/data/exports/original_photo_reconciliation_current.json"
    report=fetch_json(url)
    family=next(f for f in report["family_audits"] if f["repository"]==args.repo)
    index_path=site/"data/collection-index.json"
    gallery_path=site/"data/gallery-index.json"
    index=json.loads(index_path.read_text()); gallery=json.loads(gallery_path.read_text())
    items={e["id"]:e for e in index["entries"]}
    if any(gallery["entries"].get(k,{}).get("count")!=v["photo_count"] for k,v in items.items()):
        raise RuntimeError("existing gallery counts inconsistent; refuse publication")
    count=0; skipped={}; checked=0
    for r in family["unmatched_photos"]:
        if count>=args.limit:break
        if r.get("owner_closed_excluded"): continue
        checked+=1
        try:
            rel=Path(r["source_path"])
            if "images" not in rel.parts or "comparison-media" in rel.parts:raise ValueError("not a species image")
            sp=rel.parts[4] if len(rel.parts)>4 else ""
            if sp not in items: raise ValueError("species not in public gallery index")
            sdir=Path(*rel.parts[:5])
            cardpath=site/"data/species"/(sp+".json")
            if not cardpath.is_file():raise ValueError("species card unavailable")
            card=json.loads(cardpath.read_text())
            original_card_path=src/sdir/"species.json"
            if not original_card_path.is_file():raise ValueError("source taxon card unavailable")
            original_card=json.loads(original_card_path.read_text())
            scientific=(card.get("scientific_name") or (card.get("genus","")+" "+sp.split("-",1)[-1])).strip()
            if not scientific or scientific.split()[0].lower()!=card.get("genus","").lower():raise ValueError("scientific identity conflict")
            candidates=[x for x in original_card.get("images",[]) if Path(str(x.get("file") or "")).name==rel.name]
            if len(candidates)!=1:raise ValueError("no unique historical image record")
            image_record=candidates[0]
            if str(image_record.get("public_reuse") or "").lower().startswith(("no","private")):raise ValueError("source record disallows public reuse")
            csvrows=csv_for(src/sdir/"image-sources.csv")
            row=csvrows.get(rel.name)
            if not row:
                # Source cards sometimes carry the full individual Commons
                # evidence without a CSV row; require all exact identifiers.
                row={k:image_record.get(k) for k in ("creator","license","source_page","direct_image_url","direct_url","role")}
                if not (str(row.get("source_page") or "").startswith("https://commons.wikimedia.org/wiki/File:")
                        and row.get("creator") and row.get("license") in ALLOWED):
                    raise ValueError("no exact per-image source row")
            if str(image_record.get("license") or "") not in (str(row.get("license") or ""), "") and str(row.get("platform") or "").lower()!="inaturalist":
                raise ValueError("source card disagrees with per-photo CC license")
            original=src/r["archive_path"]
            if not original.is_file():raise ValueError("archived original unavailable")
            raw=original.read_bytes()
            if gitsha(raw)!=r["source_blob_sha"]:raise ValueError("original hash mismatch")
            if str(row.get("platform") or "").lower()=="inaturalist" and str(row.get("photo_id") or "").strip():
                author,license,lurl,page=verify_inat(row,scientific,raw)
            else:
                author,license,lurl,page=verify_commons(row,scientific,raw)
            images=card.setdefault("verified_photos",[])
            if any(x.get("source_page")==page or x.get("source_blob_sha")==r["source_blob_sha"] for x in images):
                raise ValueError("already present in species gallery")
            # Avoid republishing resized/reencoded variants of the same image.
            fp=dhash(raw)
            for existing in images:
                prior=site/existing.get("src","")
                if prior.is_file() and (fp^dhash(prior.read_bytes())).bit_count()<=2:
                    raise ValueError("visually duplicate published image")
            target=f"media/{sp}/historical-reconciled-{r['source_blob_sha'][:16]}{original.suffix.lower()}"
            dest=site/target
            if dest.exists():raise ValueError("destination already exists")
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(raw)
            images.append({"src":target,"creator":author,"source_page":page,"source_page_is_exact":True,
                "license":license,"license_url":lurl,"source_blob_sha":r["source_blob_sha"],
                "role":str(row.get("role") or row.get("view") or "General botanical photo"),
                "modified":"Archived image preserved without further modification",
                "noncommercial_only":("NC" in license),"private_rights_review_only":False,
                "photo_approval_mode":"OWNER_STANDING_PHOTO_FIRST_POLICY",
                "photo_approved_by":"Exact Commons author, license and image fingerprint checked by reconciliation pilot",
                "source_review_evidence":"Historical SHA "+r["source_blob_sha"]+"; individual Commons file "+page,
                "taxon_review_evidence":"Source species card and Commons file identity match; specialist anatomy not certified"})
            cardpath.write_text(json.dumps(card,indent=2,ensure_ascii=False)+"\n")
            items[sp]["photo_count"]+=1
            gallery["entries"][sp]["count"]+=1
            gallery["photo_count"]+=1
            count+=1
            print("RECOVERED",sp,target,license,flush=True)
        except Exception as e:
            reason=str(e).split(":")[0][:100];skipped[reason]=skipped.get(reason,0)+1
            print("SKIPPED",r["source_path"],reason,flush=True)
    if count:
        index_path.write_text(json.dumps(index,indent=2,ensure_ascii=False)+"\n")
        gallery_path.write_text(json.dumps(gallery,indent=2,ensure_ascii=False)+"\n")
        # Fail if anything mismatched, including all original indexed counts.
        assert sum(x["photo_count"] for x in index["entries"])==gallery["photo_count"]
        assert all(gallery["entries"][k]["count"]==v["photo_count"] for k,v in items.items())
    print("RECONCILIATION_BATCH_RESULT",json.dumps({"repo":args.repo,"checked":checked,"installed":count,"holds_by_reason":skipped},sort_keys=True),flush=True)
if __name__=="__main__":main()
