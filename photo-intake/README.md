# Lamiales automatic photo gallery updates

This collection already has 100 hosted approved media images plus two licensed external image links. They are retained. Its website reads `site/data/reviewed-external-photo-manifest.json`, so our automated release updates that manifest directly—not an invisible unused gallery file.

Add an image `photo-intake/approved/<species-id>/<filename>.jpg` with matching `<filename>.jpg.json` metadata **on the assigned `staging/original-source-transfer` branch**. Schema identical to [Fabaceae photo intake](https://github.com/Crking92/Hays-Botany-Fabaceae/blob/main/photo-intake/README.md). After its public reuse rights, image identity and source information are checked, a push starts the release workflow and updates Lamiales' live manifest. Both source photos and taxon records must be accurate; unknown-rights photos must NOT be uploaded to a public branch. Existing site images/lessons are never replaced.

The workflow applies to **existing indexed species**; truly new species require a species release step before their photos can be published. The legacy Hays-County-Botany library remains read-only.
