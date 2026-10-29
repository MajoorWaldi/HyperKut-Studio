# Validation scope — 29 October 2026

## Observed environment

| Item | Observation | Scope |
|---|---|---|
| GPU | NVIDIA GeForce RTX 4090, 24,564 MiB VRAM | Read from nvidia-smi on the documentation machine; not a minimum requirement. |
| Driver | 610.88 | Observed version, not a universal installation recommendation. |
| Platform | Windows / PowerShell integration | Cross-platform GPU reproduction is not qualified here. |
| Python | ComfyUI environment 3.13.12; separate release-validation Studio snapshot records 3.14 | Separate environments; do not replace the engine's packages with the Studio snapshot. |
| RAM | Not recorded in this pass | No minimum RAM claim inferred. |

## Existing evidence, not rerun in this documentation pass

The release-verification record dated 28 October reports **220 backend tests passed / 6 skipped**, **127 frontend tests passed**, a successful frontend build and **7 portable inputs across 6 presets**. It explicitly records **no GPU generation** and a clean-source snapshot rather than a clone of a published Studio repository. These counts describe that recorded snapshot, not a new test run of today's current source.

## Checks performed for this README

- Captured live Studio home, saved project and finishing controls without submitting generation or edits.
- Checked local links, copied-video hashes and media metadata.
- Prepared a smaller presentation MP4 from the verified master.
- Retained the existing technical README rather than deleting it.

## Performance

The earlier demo-production log records **107.6 seconds** to render a **100.333333-second** HyperFrames presentation at 1080×1920 / 24 fps with two workers and hardware GPU support. This is a presentation-compositing measurement, **not H3 generation speed**, and not a fresh benchmark from this documentation pass.

No reliable total H3 generation time for the fashion example has been established here. Do not derive it from file timestamps, video duration, or presentation-render speed. A release benchmark should record exact revisions, cold/warm loading, resolution, frames, steps, wall time and peak memory for each tested mode.

## Release gates still open

- Public Studio repository/download URL and complete source packaging alongside VideoTools.
- Public rights clearance for demo/source audio, references and applicable model outputs.
- A fully bundled, rights-cleared example and a clean public-clone GPU run.
- A recorded per-mode generation benchmark. Existing scripted checks do not replace it.

These are publication gates, not reasons to stop private local use or documentation work.
