#!/usr/bin/env python3
"""Family-neutral isolated new/edit species sync tests for all non-grass learners."""
import importlib.util,json,shutil,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("sync_impl",ROOT/"scripts/sync_source_species_to_site.py")
sync=importlib.util.module_from_spec(spec);spec.loader.exec_module(sync)
def main():
    idx=json.loads((ROOT/"site/data/collection-index.json").read_text())
    srcrow=next((r for r in idx["entries"] if r.get("id") and r.get("family") and r.get("genus")),None)
    assert srcrow
    family,genus=srcrow["family"],srcrow["genus"]
    sid=genus.lower()+"-automatic-qa-fixture"
    assert sid not in {x["id"] for x in idx["entries"]}
    raw={"id":sid,"family":family,"genus":genus,
         "scientific_name":genus+" test-only", "common_name":"CI generated test, not a real plant",
         "look_here_first":"CI source fixture; not a botanical identity claim",
         "morphology_keys":{"best_field_traits":["No real specimen represented"]}}
    rel=f"content/taxa/{family}/{genus}/{sid}/species.json"
    with tempfile.TemporaryDirectory(prefix="family-auto-species-") as tmp:
        folder=Path(tmp);source=folder/"source";site=folder/"site"
        shutil.copytree(ROOT/"site/data",site/"data")
        card=source/rel;card.parent.mkdir(parents=True);card.write_text(json.dumps(raw))
        dry=sync.render(source,site,[rel],check=True)
        assert dry["new_species"]==1 and not (site/"data/species"/(sid+".json")).exists()
        done=sync.render(source,site,[rel])
        assert done["new_species"]==1
        assert json.loads((site/"data/species"/(sid+".json")).read_text())["id"]==sid
        updated=json.loads((site/"data/collection-index.json").read_text())["entries"]
        assert len(updated)==len(idx["entries"])+1
        if (site/"data/gallery-index.json").exists():
            gallery=json.loads((site/"data/gallery-index.json").read_text())
            assert gallery["entries"][sid]["count"]==0 and gallery["species"]==len(updated)
        orig=srcrow["id"]
        orig_path=f"content/taxa/{family}/{genus}/{orig}/species.json"
        earlier=json.loads((site/"data/species"/(orig+".json")).read_text())
        old=source/orig_path;old.parent.mkdir(parents=True,exist_ok=True)
        doc={"id":orig,"family":family,"genus":genus,
             "scientific_name":srcrow["scientific_name"],"common_name":"Auto sync updated test name"}
        old.write_text(json.dumps(doc))
        sync.render(source,site,[orig_path])
        newer=json.loads((site/"data/species"/(orig+".json")).read_text())
        assert newer["verified_photos"]==earlier["verified_photos"]
        assert newer.get("key_traits")==earlier.get("key_traits")
        assert newer["common_name"]=="Auto sync updated test name"
        raw["family"]="Wrongaceae";card.write_text(json.dumps(raw))
        try:sync.render(source,site,[rel])
        except ValueError:pass
        else:raise AssertionError("Wrong family passed auto source publisher")
    print("PASS: auto new species, edited names, gallery integrity, curated lesson/photo preservation, wrong-family rejection")
if __name__=="__main__":main()
