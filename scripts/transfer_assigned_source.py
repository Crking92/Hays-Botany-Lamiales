#!/usr/bin/env python3
"""Copy all existing assigned family source files. Photos stay private and undisplayed."""
import hashlib,json,subprocess,sys
from pathlib import Path

src=Path(sys.argv[1]).resolve()
dst=Path(sys.argv[2]).resolve()
conf=json.loads((dst/"config/collection.json").read_text())
idx=json.loads((dst/"data/collection-index.json").read_text())
families=conf["family_assignments"]
assert conf["publication"]["enabled"] is False
assert idx["authority"]=="STAGING_ONLY"
def git(*a):return subprocess.check_output(["git","-C",str(src),*a])
head=git("rev-parse","HEAD").decode().strip()
paths=["content/taxa/"+f for f in families]
raw=git("ls-tree","-r","-z","HEAD","--",*paths)
source_files={}
for entry in raw.split(b"\0"):
 if not entry:continue
 h,p=entry.split(b"\t",1)
 parts=h.decode().split()
 assert parts[1]=="blob"
 source_files[p.decode()]=parts[2]
assert len(source_files)>100
def sha(b):return hashlib.sha1(b"blob "+str(len(b)).encode()+bytes([0])+b).hexdigest()
manifest=[]
data_count=0;media_count=0
text={".json",".csv",".txt",".md",".yml",".yaml",".tsv"}
for path,expected in sorted(source_files.items()):
 b=(src/path).read_bytes()
 assert sha(b)==expected,path
 is_data=Path(path).suffix.lower() in text
 dest=dst/path if is_data else dst/"migration/private-original-photo-holds"/Path(path).relative_to("content/taxa")
 dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists():assert dest.read_bytes()==b,path
 else:dest.write_bytes(b)
 assert sha(dest.read_bytes())==expected,path
 data_count+=int(is_data);media_count+=int(not is_data)
 manifest.append({"source_path":path,"destination":dest.relative_to(dst).as_posix(),
                  "git_blob_sha":expected,"bytes":len(b),
                  "class":"DATA" if is_data else "PRIVATE_MEDIA_HOLD"})
cards=[]
for f in sorted((dst/"content/taxa").glob("*/*/*/species.json")):
 d=json.loads(f.read_text())
 assert d["family"] in families and d["genus"]==f.parent.parent.name and d["id"]==f.parent.name
 cards.append({"id":d["id"],"scientific_name":d["scientific_name"],
  "common_name":d.get("common_name",""),"family":d["family"],"genus":d["genus"],
  "path":f.relative_to(dst).as_posix(),"photo_publication_status":"PRIVATE_ONLY_HOLD"})
assert len(cards)==conf["installed_species_baseline"],(len(cards),conf["installed_species_baseline"])
assert len({c["id"] for c in cards})==len(cards)
idx.update({"entries":cards,"source_repository":"Crking92/Hays-County-Botany",
            "source_commit_sha":head,"public_website_ready":False})
(dst/"data/collection-index.json").write_text(json.dumps(idx,indent=2,ensure_ascii=False)+"\n")
hold=dst/"migration/private-original-photo-holds"
hold.mkdir(parents=True,exist_ok=True)
(hold/"DO_NOT_PUBLISH.txt").write_text("Original source photos are preserved privately for migration only. Not for Pages or learner display.\n")
actual={p.relative_to(dst).as_posix() for p in hold.rglob("*") if p.is_file() and p.name!="DO_NOT_PUBLISH.txt"}
expected={m["destination"] for m in manifest if m["class"]=="PRIVATE_MEDIA_HOLD"}
assert actual==expected,(len(actual),len(expected))
summary={"status":"ALL_ASSIGNED_FAMILY_ORIGINAL_FILES_BYTE_EXACT_PRIVATE",
 "repository":conf["repository_full_name"],"source_commit":head,
 "families":families,"species":len(cards),"total_original_files":len(manifest),
 "original_text_files":data_count,"source_media_private_quarantine":media_count,
 "original_files_missing":0,"public_site_deployed":False,"hub_unchanged":True}
(dst/"migration/original-source-transfer-manifest.json").write_text(json.dumps(
 {"summary":summary,"files":manifest},indent=2,ensure_ascii=False)+"\n")
(dst/"migration/original-source-transfer-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print("ALL_ASSIGNED_SOURCE_TRANSFER_PASS",json.dumps(summary,sort_keys=True),flush=True)
