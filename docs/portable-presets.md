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

## Media policy

Only include assets with explicit redistribution permission recorded in the bundle's rights manifest. Missing or withheld sources must be supplied by the user. Generated previews need their own output/source/audio review; a successful generation or creator credit is not permission.

The bundle mechanism preserves input integrity and refuses an existing nonempty workspace. It is not a project-history migration or merge tool.
