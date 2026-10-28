#!/usr/bin/env python3
"""Read-only pre-migration validation of a Hays Botany family collection."""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def fail(message):
    raise SystemExit("COLLECTION_VALIDATION_FAILED: " + message)


def read(path):
    try:
        return json.loads((ROOT / path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(f"{path}: {exc}")


def main():
    config = read("config/collection.json")
    index = read("data/collection-index.json")
    repo = str(config.get("repository_full_name", ""))
    env_repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo.startswith("Crking92/Hays-Botany-"):
        fail("invalid repository name")
    if env_repo and env_repo != repo:
        fail(f"configuration repository {repo} does not match {env_repo}")
    if config.get("planning_status") != "STAGING_ONLY_NOT_AUTHORITATIVE":
        fail("unexpected authority status; review before changing publication gates")
    if config.get("canonical_repository_until_approved_handoff") != "Crking92/Hays-County-Botany":
        fail("canonical source handoff attempted without approval")
    if config.get("publication", {}).get("enabled") is not False:
        fail("publication must remain disabled in staging")
    if config.get("navigation_contract", {}).get("published_site_url") is not None:
        fail("no live family URL is authorized at setup stage")
    families = config.get("family_assignments")
    if not isinstance(families, list) or not families or len(families) != len(set(families)):
        fail("family assignments empty, duplicated, or invalid")
    if any(not re.fullmatch(r"[A-Z][a-z]+aceae", f) for f in families):
        fail("invalid family name in assignments")
    if config.get("schema_version") != 1 or index.get("schema_version") != 1:
        fail("unsupported schema version")
    if not config.get("collection_id") or index.get("collection_id") != config["collection_id"]:
        fail("collection ID mismatch")
    if index.get("authority") != "STAGING_ONLY":
        fail("catalog cannot declare authority during setup")
    entries = index.get("entries")
    if not isinstance(entries, list):
        fail("catalog entries must be an array")
    cards = sorted((ROOT / "content/taxa").glob("*/*/*/species.json"))
    if len(entries) != len(cards):
        fail(f"catalog has {len(entries)} entries but {len(cards)} species.json files")
    seen = set()
    for row in entries:
        if not isinstance(row, dict):
            fail("catalog entry is not an object")
        sid, fam, genus, path = (row.get(k) for k in ("id", "family", "genus", "path"))
        if not isinstance(sid, str) or not SLUG.fullmatch(sid):
            fail("invalid species ID")
        if sid in seen:
            fail(f"duplicate species ID: {sid}")
        seen.add(sid)
        if fam not in families:
            fail(f"unassigned family for {sid}: {fam}")
        expected = f"content/taxa/{fam}/{genus}/{sid}/species.json"
        if path != expected or not (ROOT / expected).is_file():
            fail(f"invalid/missing species file for {sid}")
        card = read(path)
        if card.get("id") != sid or card.get("family") != fam or card.get("genus") != genus:
            fail(f"species card identity/family mismatch: {sid}")
        if row.get("scientific_name") != card.get("scientific_name"):
            fail(f"catalog scientific name out of sync: {sid}")
    print(json.dumps({
        "result": "PASS_STAGING_ONLY",
        "repository": repo,
        "assigned_families": len(families),
        "indexed_species": len(entries),
        "physical_species_cards": len(cards),
        "published": False,
        "source_authority_unchanged": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
