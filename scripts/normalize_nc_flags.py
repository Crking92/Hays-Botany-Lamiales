#!/usr/bin/env python3
"""Repair stale site-specific CC-NC restriction flags without changing source rights."""
from pathlib import Path
import json
if __name__ == "__main__":
    total=0
    changed_species=0
    for path in sorted(Path("site/data/species").glob("*.json")):
        card=json.loads(path.read_text())
        n=0
        for photo in card.get("verified_photos",[]):
            is_nc=photo.get("license") in {"CC BY-NC 4.0","CC BY-NC-SA 4.0"}
            if photo.get("noncommercial_only") is not is_nc:
                photo["noncommercial_only"]=is_nc
                n+=1
        if n:
            path.write_text(json.dumps(card,indent=2,ensure_ascii=False)+"\n")
            changed_species+=1
            total+=n
            print("NC_FLAG_CORRECTED",path.stem,n,flush=True)
    print("NC_FLAG_TOTAL",total,"species",changed_species)
