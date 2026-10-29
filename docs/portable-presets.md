# Portable preset inputs

Added 2026-10-28. This mechanism does not copy workspace history or infer media rights.

## Build a redistribution bundle

The publisher maintains a private rights ledger keyed by the **SHA-256 of each input file**. An asset is included only with `redistribute: true`, an explicit license/permission statement and evidence. A filename, upload ID or successful generation is not permission.

Example ledger structure (the example grants no rights):

```json
{"assets":{"FULL_SHA256":{"redistribute":false,"license":"Pending","evidence":"Pending"}}}
```

From the Studio source directory:

```powershell
python scripts/preset_bundle.py build --rights D:\private\rights.json --output D:\release\preset-bundle
```

The output is a folder containing `manifest.json`, six preset JSON files and only cleared input assets. IDs are derived from content hashes, so they are independent of the publisher's upload database. Sparse reference slots and settings are preserved. Uncleared/missing inputs become empty slots and are listed in `withheld`. Generated previews, reference covers and source job IDs are omitted: output rights must be reviewed separately, including the video model and any retained source soundtrack.

## Install before the first Studio start

```powershell
python scripts/preset_bundle.py verify --bundle D:\release\preset-bundle
python scripts/preset_bundle.py install --bundle D:\release\preset-bundle
```

Run these commands from the new Studio source directory, before its first launch. `--studio-root` selects a different installation. The installer verifies every asset's hash, kind and path before writing, then registers inputs in the fresh workspace and replaces the bundled preset JSON files with their portable versions. **An existing nonempty workspace is refused**. Do not use this tool as a migration/merge utility for an established Studio.

Start the Studio normally afterwards. Inputs resolve through the existing `/api/uploads/` routes and remain available after restart. A Remix preset whose source was withheld still requires the user to upload their own reference video; Music requires a supplied track if none was cleared.

## Current release decision

The participant expressly authorized redistribution of the two music tracks and five generated portraits on 2026-10-28. The private ledger records that attestation and each file's digest; this is author permission, not an invented CC0 or MIT license over the media. Model/platform and third-party rights remain applicable.

The two Remix source videos were not byte-identical to the `ref_##` files whose use was previously authorized. Neither is distributed. No generated preview is included while H3 output rights and, where relevant, source-video/music clearance remain unresolved. The active private Studio keeps all its media and previews.

Checks: bundle API round trip after restart, missing permission, tampering, path escape and refusal to overwrite an existing workspace. A separate fresh source snapshot also served all seven cleared inputs for all six presets after two starts. No new GPU generation was required.
