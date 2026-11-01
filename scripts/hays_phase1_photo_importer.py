#!/usr/bin/env python3
"""One-off Phase 1 archive installer for Hays family staging branches.

Reads the already-committed licensed-photo manifests, verifies original pixel
hashes from remote source, resizes for the learner, replaces external image
references with repository-local files, and keeps creator/source/license data.
Does not publish Pages, change branches or start a recurring automation.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlsplit
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / 'migration/incoming-photo-batches/2026-11-01'
ALLOWED = {'inaturalist-open-data.s3.amazonaws.com', 'collections.nmnh.si.edu', 'was.tacc.utexas.edu'}
MAX_BYTES = 25 * 1024 * 1024
VALID_LICENSE = ('creativecommons.org/licenses/by/4.0/', 'creativecommons.org/licenses/by-nc/4.0/',
                 'creativecommons.org/licenses/by-sa/4.0/', 'creativecommons.org/publicdomain/zero/1.0/')


def fetch_exact(photo: dict) -> bytes:
    url = photo['image_url']
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED or parsed.username:
        raise ValueError('Unsupported/HTTP photo source URL; keep exact original ZIP archive')
    lc = urlsplit(photo.get('license_url', ''))
    if lc.hostname not in ('creativecommons.org','www.creativecommons.org') or not any(
        v in lc.path for v in ('/licenses/by/4.0/', '/licenses/by-nc/4.0/', '/licenses/by-sa/4.0/', '/publicdomain/zero/1.0/')
    ):
        raise ValueError('License not on approved CC source list')
    req = urllib.request.Request(url, headers={'User-Agent':'HaysBotanyEducationalPhotoImporter/1.0'})
    with urllib.request.urlopen(req, timeout=32) as resp:
        raw=resp.read(MAX_BYTES + 1)
    if len(raw)>MAX_BYTES:
        raise ValueError('Source photo too large')
    actual=hashlib.sha256(raw).hexdigest()
    if actual!=photo['sha256']:
        raise ValueError('Original source SHA mismatch; do not substitute a different photo')
    return raw


def local_jpeg(raw: bytes) -> bytes:
    with Image.open(io.BytesIO(raw)) as im:
        if im.format not in {'JPEG','PNG','WEBP','TIFF'}:
            raise ValueError('Unexpected image format')
        im=ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((1600,1600),Image.Resampling.LANCZOS)
        output=io.BytesIO()
        im.save(output,format='JPEG',quality=82,optimize=True)
    return output.getvalue()


def install_one(data: dict, sp: dict, report: list) -> None:
    fam=data['family']
    genus=sp['species'].split(' ')[0]
    slug=sp['species_id']
    species_file=ROOT/'content'/'taxa'/fam/genus/slug/'species.json'
    if not species_file.is_file():
        report.append({'species':sp['species'],'error':'Species card missing; held'});return
    card=json.loads(species_file.read_text(encoding='utf8'))
    if card.get('family')!=fam or card.get('id')!=slug or card.get('scientific_name','').casefold()!=sp['species'].casefold():
        report.append({'species':sp['species'],'error':'Family/name/id mismatch; held'});return
    old=card.setdefault('images',[])
    successful=0; pending=[];changed=False
    for p in sp['photos']:
        key=p['sha256']
        local_path='images/phase1-' + key[:20]+'.jpg'
        dest=species_file.parent/local_path
        match=next((im for im in old if im.get('original_source_sha256')==key or im.get('file')==p['image_url']),None)
        if dest.exists() and match and match.get('file')==local_path:
            successful+=1;continue
        try:
            raw=fetch_exact(p)
            dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():
                dest.write_bytes(local_jpeg(raw))
            if match is None:
                l=p['license_url']
                license_name='CC0 1.0' if 'publicdomain/zero/' in l else 'CC BY-NC 4.0' if '/by-nc/' in l else 'CC BY-SA 4.0' if '/by-sa/' in l else 'CC BY 4.0'
                match={'role':'Phase 1 source photo; anatomy not yet manually verified',
                       'creator':p['creator'],'license':license_name,'license_url':l,
                       'source_page':p['source_url'],'source_platform':'GBIF/inaturalist',
                       'original_source_sha256':key,'media_source_url':p['image_url'],
                       'photo_review':'Exact original pixels hash checked; identity and source license still require photo-specific review before publication',
                       'anatomy_arrows':'not added'}
                old.append(match)
            match['file']=local_path
            match['hosting_status']='GITHUB_HOSTED_STAGING_ONLY_NOT_PUBLISHED'
            match['modifications']='Downscaled to 1600px maximum; JPEG conversion; EXIF stripped'
            match['original_source_sha256']=key
            changed=True
            successful+=1
        except Exception as exc:
            pending.append({'sha256':key,'reason':str(exc)[:180], 'source_url':p['image_url']})
    if changed or (card.get('phase1_photo_batch') is not None):
        status=card.setdefault('phase1_photo_batch',{})
        status.update({'date':'2026-11-01','source_family':fam,'incoming_photo_count':len(sp['photos']),
                       'github_hosted_count':successful,'pending_count':len(pending),
                       'github_hosted_copy_completed':successful==len(sp['photos']),
                       'preserved_original_zip_in_chatgpt_library':True,
                       'deployment_status':'STAGING_ONLY_NO_PUBLIC_SITE_CUTOVER'})
        species_file.write_text(json.dumps(card,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    report.append({'species':sp['species'],'hosted':successful,'pending':pending})


def main():
    report=[]
    for manifest in sorted(MANIFESTS.glob('*-photo-provenance.json')):
        data=json.loads(manifest.read_text(encoding='utf8'))
        for species in data.get('species',[]):
            install_one(data,species,report)
    output=MANIFESTS/'phase1-import-report.json'
    output.write_text(json.dumps({'schema_version':1,'report':report},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'species':len(report),'hosted':sum(x.get('hosted',0) for x in report),
                      'pending':sum(len(x.get('pending',[])) for x in report),'details':report},indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())