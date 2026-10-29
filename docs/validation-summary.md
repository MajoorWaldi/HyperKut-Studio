# Validation and testing

The Studio is beta. Automated checks validate specific contracts; they do not certify artistic quality, model identity fidelity, every browser or every GPU configuration.

## Run the checks

From the Studio directory, using its own environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
Push-Location frontend
npm ci
npm test
npm run build
npm run lint
Pop-Location
```

## Existing evidence

A 28 October 2026 clean-source validation record reports 220 backend tests passed / 6 skipped, 127 frontend tests passed and a successful frontend build, plus seven preset inputs served across six presets. This is dated evidence for that snapshot, not a new test run or a public-clone GPU qualification.

The demonstrated local environment uses Windows and an RTX 4090 with approximately 24 GB VRAM. This is an observed configuration, not a minimum hardware guarantee. Memory and performance depend on model variants, offloading, resolution and duration.

## Qualification priorities

- Full model-backed generation from a clean published installation.
- Per-mode cold/warm timings and memory measurements with exact model revisions.
- Narrative continuity, identity and product consistency on real generated sequences.
- Experimental finishing across aspect ratios; preview/export agreement and timeout recovery.
- Manual montage and new-take/extension interactions, media portability and browser coverage.

The README walkthrough is simulated and cannot establish inference speed or completed regeneration. See [presentation provenance](demo-production.md) and the [roadmap](../ROADMAP.md).
