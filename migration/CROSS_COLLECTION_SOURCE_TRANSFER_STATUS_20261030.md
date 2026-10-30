# Cross-collection source migration status — October 30, 2026

## October 30 later update — all eight grouped collections live-file QA finished

**Eight-group existing-source migration sweep: COMPLETE.** The 4,982 original files across 899 species remain accounted for; the six grouped collections previously awaiting live Pages tests have now all passed an automated independent HTTP/byte check of **every published species JSON and every hosted gallery image**. Together with the two earlier verified collections, all eight groups have a successful deployed-photo verification run. The six newer tests independently compare each published photo's Git blob hash with the archived source hash, check credit/license fields, compare indexes and inspect the actual Pages-served JSON/media bytes. The previous paragraph below saying those six had not yet been independently re-fetched is **superseded by this dated addendum**.

| Family-group website | Species | Original source files exact | Hosted gallery photos | Live gallery QA |
|---|---:|---:|---:|---|
| Fabaceae | 91 | 491/491 (four documented text/credit edits) | 88 | [PASS 41063761970](https://github.com/Crking92/Hays-Botany-Fabaceae/actions/runs/41063761970) |
| Lamiales | 102 | 582/582 | 100 (+ 2 approved remote photo links) | [PASS 41078124849](https://github.com/Crking92/Hays-Botany-Lamiales/actions/runs/41078124849) |
| Monocots & Aquatics | 113 | 587/587 | 35 | [PASS 41081040579](https://github.com/Crking92/Hays-Botany-Monocots-Aquatics/actions/runs/41081040579) |
| Asterid Allies | 118 | 693/693 | 64 | [PASS 41081440106](https://github.com/Crking92/Hays-Botany-Asterid-Allies/actions/runs/41081440106) |
| Cacti & Buttercups | 107 | 543/543 | 37 | [PASS 41081592865](https://github.com/Crking92/Hays-Botany-Cacti-Buttercups/actions/runs/41081592865) |
| Spurges & Mallows | 130 | 764/764 | 99 | [PASS 41081608621](https://github.com/Crking92/Hays-Botany-Spurges-Mallows/actions/runs/41081608621) |
| Trees & Shrubs | 133 | 790/790 | 107 | [PASS 41081682522](https://github.com/Crking92/Hays-Botany-Trees-Shrubs/actions/runs/41081682522) |
| Mixed Families | 105 | 532/532 | 19 | [PASS 41081696484](https://github.com/Crking92/Hays-Botany-Mixed-Families/actions/runs/41081696484) |
| **Totals** | **899** | **4,982/4,982 accounted for** | **549** (+ 2 remote Lamiales) | **8/8 pass** |

Each of the six newly audited collections has a README reflecting its PUBLIC photo-backed state, a migration checkpoint under `migration/`, and an `scripts/verify_existing_site.py` with a GitHub Actions live-site QA workflow. Tiny photo-caption copy errors that falsely said unchanged original photos were resized were corrected. No original photos, legacy hub data, or historic photo archive were deleted or modified.

**Data-enrichment backlog, not a migration defect:** the six new QA runs report **16 inherited empty `look_here_first` fields** (Asterid Allies 14; Cacti & Buttercups 2; Monocots, Spurges, Trees, Mixed 0). These species records and any other missing anatomy or diagnostic content remain for a separate botanical improvement phase. Do not fabricate missing lessons merely to make source-transfer metrics pass.

**Open non-migration concerns:** historical held photo bytes in public Git history are not made private by Pages filtering; individual photo-rights/provenance still need their own review before additional public gallery inclusion. The original Hays-County-Botany stays read-only, old scheduled automations stay paused, and the final unified hub/navigation cutover and further botanical improvements are separate future steps. Poaceae and Asteraceae are separate previously migrated specialist families and were not re-audited by this eight-group verification.


**Scope:** Existing botanical records and existing photographs ONLY. No new photos, new taxa, new source science, new location work, family-to-hub website cutover, or automation restarts. The original `Crking92/Hays-County-Botany` remains READ-ONLY botanical fallback. This report records preserved SOURCE BYTES separately from approved/public photos.

## Eight source-transfer audit results (original hub vs assigned family staging branches)

Every row below was checked against the original hub's Git blob SHA and the destination staging tree SHA. The four differences in Fabaceae are intentional corrections to photographic source-credit metadata, not missing file transfers.

| Family collection | Species | Original source files present | Source photos preserved | Public site species cards | Existing published hosted photos |
|---|---:|---:|---:|---:|---:|
| Fabaceae | 91 | 491 / 491 (487 unchanged + 4 credit edits) | 200 | 91 | 88 |
| Lamiales (11 assigned families) | 102 | 582 / 582 exact | 240 | 102 | 100 (plus 2 licensed remote references) |
| Monocots–Aquatics | 113 | 587 / 587 exact | 205 | 113 | 35 |
| Asterid Allies | 118 | 693 / 693 exact | 306 | 118 | 64 |
| Cacti–Buttercups | 107 | 543 / 543 exact | 194 | 107 | 37 |
| Spurges–Mallows | 130 | 764 / 764 exact | 347 | 130 | 99 |
| Trees–Shrubs | 133 | 790 / 790 exact | 320 | 133 | 107 |
| Mixed Families | 105 | 532 / 532 exact | 170 | 105 | 19 |
| **Combined** | **899** | **4,982 / 4,982 accounted for** | **1,982** | **899** | **549** |

**Important:** the original photo count represents archived source binaries, not a promise that each image may legally be displayed publicly or is suitable for a diagnostic panel. Held source originals in each public family repository's branches are still repository-visible. Rights gates are publication rules, not reasons to mark the family source transfer incomplete.

All eight family public sites already contain their full corresponding collection's species index and some published photographs; no six-repository rebuild from an empty preview is needed. The per-repository `site/data/gallery-index.json` species and photo counts match the actual Git tree's `site/data/species/*.json` and `site/media/*` file counts during this audit. The Lamiales [100-photo live byte/hash QA](https://github.com/Crking92/Hays-Botany-Lamiales/actions/runs/41078124849) and Fabaceae [88-photo live QA](https://github.com/Crking92/Hays-Botany-Fabaceae/actions/runs/41063761970) have separately passed. The remaining six websites have valid main-branch Pages deployments and gallery manifests, but **their latest photo files were not all independently re-fetched from Pages in this turn**. Do that separate live test before claiming 100% live end-to-end readiness for those six.

## Two separately migrated specialist collections

- **Poaceae**: 112/112 grass species have source photographs and the dedicated photo learner; its historical [closeout report](https://github.com/Crking92/Hays-Botany-Poaceae/blob/main/migration/POACEAE_FAMILY_SOURCE_PHOTO_CLOSEOUT_20261029.md) reports 486 referenced photo files, 604 teaching panels, zero grass species lacking source photographs. Its source migration was done earlier and is not part of the 4,982-file re-audit.
- **Asteraceae**: 180 original species and public site with 172 hosted source photos across 124 species according to [its existing QA checkpoint](https://github.com/Crking92/Hays-Botany-Asteraceae/blob/main/migration/ASTERACEAE_EXISTING_SOURCE_RECOVERY_CHECKPOINT_20261029.md). Its source bytes were previously migrated and are not part of the 4,982-file re-audit.
- Together the eight grouped collections plus Poaceae and Asteraceae account for **1,191 species across the 10 assigned family repositories**. Preserve original provenance. This report does not assert a new byte-for-byte comprehensive Poaceae/Asteraceae source audit.

## A note on red GitHub Actions jobs

Several grouped repositories had unsuccessful historical runs labeled **'Publish existing ... text learner (NO original photos)'**. Review of Monocots–Aquatics and Asterid Allies job logs established that these failures resulted from an intentional safety guard:

`BLOCKED: photo-backed family learner is active. Do not overwrite it with an old text-only release. Use the source-aware photo gallery workflow.`

This is the correct outcome, not loss of source data. The corresponding Pages deployments succeeded. **Do not rerun or bypass the obsolete text-only workflow** to make its old job turn green; that would replace photo-backed lessons with a text-only release.

## What to do next

**Close Fabaceae's source transfer** and continue with already staged Lamiales/public-website validation, then the other six grouped repositories in a systematic existing-data QA sweep. Do not spend the migration phase harvesting new photos or writing new botanical content. The publicly visible existing gallery is a rights-filtered view; hold questionable source photos without deleting or overwriting original image bytes. Each family is the editorial destination under the [active routing registry](https://github.com/Crking92/Hays-County-Botany/blob/main/workflow/ACTIVE_NEW_PLANT_WRITE_ROUTING_20261028.json); leave the hub old-records read-only.

Related:
- [Fabaceae source transfer completion](https://github.com/Crking92/Hays-Botany-Fabaceae/blob/main/migration/FABACEAE_TRANSFER_COMPLETE_HANDOFF_20261030.md)
- [Lamiales source and live site audit](LAMIALES_TRANSFER_READY_HANDOFF_20261030.md)
