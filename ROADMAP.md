# HyperKut Studio — beta roadmap

The entire Studio is **beta**. Finishing is **experimental** and disabled by default. This roadmap distinguishes implemented features from qualification work and future ideas; priorities are not release-date commitments.

## Implemented in the beta

| Capability | Current scope |
|---|---|
| Remix, Text and Music | ComfyUI workflows driven through the Comfy SDK and local API proxy. |
| Reference-driven creation | Up to five image inputs, a source/reference video where applicable, creative brief and artistic direction. |
| Shot workflow | Per-shot prompts, retained takes, regeneration, source-window selection and export. |
| Manual montage | Shared Timeline Edit adapter: trim/slip, cuts, reordering, duplication, take selection, undo/redo and export. |
| Music direction | YuE2 for new music, supplied-track mode, waveform preview and measured timing guidance. |
| Projects and presets | Local persistence, project ZIP export/import with validated media remapping, and a rights-gated portable preset-input bundle. |
| Interface | English/French, progressive image inputs, optional controls, stop/restart controls and notifications. |
| Formats and quality | Portrait, square and landscape; Draft, Standard, Max and XHigh. XHigh is approximately 1.5 MP generation, not 4K upscaling. |

## Experimental features

- Finishing: internal sub-cuts, visual effects, animated text, motion graphics, sound design and sound effects. Review every export.
- Unified HyperFrames compositor, shot-local timing, word reveals and musical-onset alignment.
- Opt-in `tech`, `editorial` and `pop` graphic-layer packs and subject-derived accent color. Implementation exists; broader rendered-output qualification and creative refinement remain.
- Optional location plates and subject masks for applicable branches.
- AI extension candidates behind `HYPERKUT_EXPERIMENTAL_AI_EDIT=1`: review/accept/reject before changing the active take. This is not a qualified general-purpose extension workflow.

## Near-term priorities

- [ ] Reproduce a full GPU workflow from a clean installation with pinned model revisions and authorized example inputs.
- [ ] Improve narrative continuity, viewpoint diversity, one-time actions and product/character consistency across dense edits.
- [ ] Improve musical phrasing and alignment without interrupting protected continuous actions.
- [ ] Qualify experimental finishing across aspect ratios and browsers, including render failure recovery and preview/export agreement.
- [ ] Improve diagnostics, portable assets and first-run setup; document measured performance per mode.
- [ ] Add regression coverage when the manual montage, new takes and experimental extensions interact.

## Future exploration — not currently integrated

- Continuous narrator audio with script-to-scene timing; local speech transcription and editable subtitles.
- Dedicated talking-character/lip-sync evaluation, translation and voice-preserving dubbing.
- Data-driven charts, numeric counters and infographic layouts.
- Semantic highlights from longer videos and subject-aware reframing of finished edits.
- Additional selectable video backends, integrated 4K upscaling and project ZIP import.
- Product/brand URL intake and optional conversational orchestration.

## Operating limits

Windows is the documented integration path. Studio and ComfyUI share the media/output disk; changing the SDK URL alone does not establish remote deployment. Keep localhost binding: public hosting requires authentication, quotas and isolation not supplied by the normal local setup.

Generated identity, motion, narration and musical fit need human review. Technical take checks are not semantic quality certification. Some reference effects are approximated. Model/dependency/media terms remain separate from the MIT application license.

[User guide](docs/usage.md) · [Known limits](docs/known-issues-and-roadmap.md) · [Validation](docs/validation-summary.md) · [Licenses](LICENSES.md)
