# Changelog

## Current beta

- Remix, Text and Music creation through local ComfyUI and the Comfy SDK.
- Project library, presets, five visual references and English/French interface.
- Per-shot prompts, regeneration, retained takes, source-window selection and export.
- Shared manual montage editor with trim/slip, cuts, take selection and undo/redo.
- Experimental unified graphics, text/effects and sound finishing, disabled by default.
- Official presentation and a separately labelled simulated README walkthrough.
- Automatic export check: duration, ratio, audio track and, for Remix, cut count against the reference are compared with the request; findings show as warnings.
- Planned text is drawn by the assembler when HyperFrames is not available.
- In a remote or jury Studio the SFX library must sit inside `HYPERKUT_SFX_ROOT`.
- New projects default to adaptive rhythm, automatic cut pace and 100% musical synchronization.
- The job waveform reads audio in blocks instead of loading it whole.

See [roadmap](ROADMAP.md) for status and [known limits](docs/known-issues-and-roadmap.md) for qualification boundaries.
