#!/usr/bin/env python3
"""Isolated Lamiales ingestion; never edits real site source."""
import json,shutil,tempfile,subprocess,sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
PUBLISH=ROOT/"scripts/publish_approved_lamiales_photos.py"
SID="monarda-citriodora"
def call(source,site,approved=True,check=False):
    cmd=[sys.executable,str(PUBLISH),"--source-root",str(source),"--site-root",str(site)]
    if check:cmd.append("--check")
    p=subprocess.run(cmd,text=True,capture_output=True)
    if (p.returncode==0)!=approved:raise AssertionError(p.stdout+p.stderr)
    return json.loads(p.stdout) if approved else {}
def main():
    origin=ROOT/"site/data/reviewed-external-photo-manifest.json"
    initial=json.loads(origin.read_text())
    assert len(initial["species"])==55
    local=ROOT/"site/media/monarda-citriodora/01-reference.jpg"
    assert local.is_file()
    with tempfile.TemporaryDirectory(prefix="lamiales-auto-photo-") as temp:
        d=Path(temp); site=d/"site";source=d/"source"
        shutil.copytree(ROOT/"site",site)
        folder=source/"photo-intake/approved"/SID
        folder.mkdir(parents=True)
        photo=folder/"qa-existing-monarda-crop.jpg"
        with Image.open(local) as im:
            im.crop((0,0,min(im.width,350),min(im.height,350))).convert("RGB").save(photo,quality=90)
        original=initial["species"][SID][0]
        sidecar=photo.with_name(photo.name+".json")
        info={"species_id":SID,"photo_file":photo.name,
              "status":"APPROVED_FOR_PUBLIC_FAMILY_SITE",
              "rights_approved_for_public":True,"taxon_reviewed":True,
              "approved_by":"Isolated QA fixture only",
              "approval_note":"Test crop of previously published licensed source bytes, not real upload",
              "creator":original["creator"],"source_page":original["source_page"],
              "source_page_is_exact":True,"license":"CC BY 4.0",
              "license_url":"https://creativecommons.org/licenses/by/4.0/",
              "role":"Existing Monarda flower and leaf anatomy test crop",
              "modifications":"QA-only crop"}
        sidecar.write_text(json.dumps(info))
        assert call(source,site,check=True)["installed"]==1
        assert not (site/"media"/SID/photo.name).exists()
        result=call(source,site)
        assert result["installed"]==1
        new=json.loads((site/"data/reviewed-external-photo-manifest.json").read_text())
        assert len(new["species"][SID])==len(initial["species"][SID])+1
        assert sum(map(len,new["species"].values()))==sum(map(len,initial["species"].values()))+1
        assert call(source,site)["installed"]==0
        info["rights_approved_for_public"]=False;sidecar.write_text(json.dumps(info))
        call(source,site,approved=False,check=True)
        info["rights_approved_for_public"]=True
        info["species_id"]="wrong-species";sidecar.write_text(json.dumps(info))
        call(source,site,approved=False,check=True)
    assert json.loads(origin.read_text())==initial
    print("PASS: correct Lamiales photo manifest, duplicate handling, rights and taxon failures")
if __name__=="__main__":main()
