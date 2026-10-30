# Lamiales — migration source audit and live website verification (October 30, 2026)

## Migration-only phase: status and operating scope

**SOURCE FILES TRANSFERRED: 582/582 byte-for-byte.** This checkpoint starts the family-group audit following Fabaceae. It does **not** authorize collecting new photographs, adding new botanical data, relaxing license exclusions, restarting automations, or changing the legacy hub. Existing source data are preserved in this family repository's `staging/original-source-transfer` branch; the existing `main/site` is a separately filtered, already-published photo learner.

This source-only audit compared all **582 entries** in `migration/original-source-transfer-manifest.json` against the original `Crking92/Hays-County-Botany` main tree and the Lamiales staging tree: **582/582 original Git blob SHAs match both trees**. There are **zero source-transfer discrepancies**. These 582 files include **342 botanical species/source/credit text files and 240 original photo binaries**, assigned across 102 species in 11 families: Acanthaceae, Bignoniaceae, Lamiaceae, Lentibulariaceae, Martyniaceae, Oleaceae, Orobanchaceae, Paulowniaceae, Plantaginaceae, Scrophulariaceae, Verbenaceae.

The **240 source photo binaries** are transferred and preserved in the family source/rights-hold archive. They should never be conflated with the narrower **100** licensed originals published as `site/media` assets. Archived-but-not-published photographs remain accounted for, not lost, and should not be displayed without matching individual rights.

## Current public family learner

- **102/102** species pages and collection-index entries already present.
- **102** approved gallery photo *references* across **55 species**, of which **100** photographs are locally served by the family Pages site and **2** remain directly linked, licensed Commons source images.
- The published original image file SHA matches the recorded `source_blob_sha` for **100/100** hosted photographs.
- [Live public photo verification run 41078124849](https://github.com/Crking92/Hays-Botany-Lamiales/actions/runs/41078124849) **PASSED** after upgrading its checks to verify all 102 species, all 100 existing hosted photo files and original byte-for-byte Git hashes, and after adding temporary Pages HTTP 5xx retry handling.
- **158 of 260 original source image metadata references** remain intentionally held: 123 rights/license-version insufficiencies, 23 remote/nonlocal file paths, 7 image-specific provenance gaps, and 5 publishing-permission gaps. These are *gallery eligibility holds*, not a missing-source migration.
- **47 species** have no published photo reference yet. Collecting new imagery, improving identification quality, or resolving held-rights photos belongs to a later enrichment phase.

## Handoff rules

- **No additional data/photo collection** during the cross-family source migration. Preserve **all original** species records, text, credits, photo bytes and source-image references as-is, whether or not public display is allowed.
- New/edited Lamiales botanical records route to `Crking92/Hays-Botany-Lamiales`, branch `staging/original-source-transfer`, following the active multi-repo routing registry in the old hub; the old hub stays a read-only fallback.
- Public photos remain only the already approved, properly attributed subset; all-rights-reserved, noncommercial-conditional, private-study-only, missing-permission or ambiguous photos remain in their legacy archive/hold state. Do not assume repository visibility implies publication rights.
- No paused automation restart and no original-hub changes.
- Future optional work: photo diagnostics, source-rights enrichment, missing gallery photos, botanical cards, comparisons, arrows, and hub navigation release. None of these blocks **source transfer completion**.

**Fabaceae previous completed collection:** [491/491 source migration completion handoff](https://github.com/Crking92/Hays-Botany-Fabaceae/blob/main/migration/FABACEAE_TRANSFER_COMPLETE_HANDOFF_20261030.md).

**References:** [Lamiales manifest](https://github.com/Crking92/Hays-Botany-Lamiales/blob/staging/original-source-transfer/migration/original-source-transfer-manifest.json), [photo publication scope](../site/PHOTO_PUBLICATION_SCOPE.md), [approved photo manifest](../site/data/reviewed-external-photo-manifest.json).
