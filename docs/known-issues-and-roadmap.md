# SECATOR — known limits and roadmap

Reviewed **27 October 2026**. The [full capability matrix and checklist](../../ROADMAP.md) is maintained at the VideoTools pack root ([repository location](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools/blob/main/ROADMAP.md)). The roadmap describes current implementations and planned work; it does not imply release dates or quality parity with Higgsfield.

## Available, with review limits

- [x] Local Remix, Text and Music workflows; H3 takes, YuE2 music, Tone.js SFX and unified HyperFrames finishing.
- [x] EN/FR Studio, five image references, per-shot prompt editing/regeneration, take selection, re-editing and project persistence.
- [x] Shot-local H3 prompts, explicit narrative state handoffs and set-dressed location references.
- [x] Animated words, shared safe areas, reading-time advisories and shot-bounded musical onset alignment.
- [x] Adaptive dynamic-edit planning: remove the 1.2 s-per-take ceiling, distinguish independent takes from editorial cuts, and use Music grid timings as a guide rather than imposing one take every three seconds.
- [x] Fifteen-second CPU montage with twenty segments and three-frame accents. This validates editing mechanics, not twenty H3 viewpoints or artistic narrative quality.
- [x] Six creative audition exports. Selection and conversion into presets remain pending; the old presets were removed deliberately.

## Next — improve what exists

- [ ] Evaluate count adherence, viewpoint diversity and continuity on real generated dense edits, not only deterministic montage checks.
- [ ] Improve one-time actions, prop-state handoffs, face/outfit/product consistency and long sequences; human review remains necessary.
- [ ] Improve full-edit musical phrasing and measured sync without imposing a genre, mandatory drop or cuts through protected gestures.
- [ ] Finish style-specific motion packs, subject-derived accent colors, numeric counters and infographic data handling.
- [ ] Broaden graphic preview/render-performance coverage; keep optional diagnostics out of the ordinary creative flow.
- [ ] Clarify uploaded-reference roles without complicating the five existing inputs. A scene reference is guidance, not an exact first frame.
- [ ] Select/rework the best audition videos, then create EN/FR presets and authorized demo assets.

## Next — complete short-video workflows

- [ ] Continuous narration track with script-to-scene timing, one narrator identity, pauses and ducking.
- [ ] Local speech transcription and phrase/word alignment; editable animated subtitles and subtitle export.
- [ ] End-to-end narrated explainer/faceless workflow using scenes, narration, captions and music.
- [ ] Dedicated UGC/talking-character flow with explicit voice and lip-sync evaluation.
- [ ] Structured animated charts, diagrams, accurate counters and reusable infographic layouts.

## Later

- [ ] Semantic highlight selection from long local videos; optional authorized YouTube/URL ingestion. Scene boundaries alone do not identify the best moment.
- [ ] Finished-video subject-aware reframing, with text/composition review in social formats.
- [ ] Translation and voice-preserving dubbing, distinct from the already localized interface.
- [ ] Product URL/brand intake with editable extracted data and media provenance.
- [ ] Optional integrated 4K upscale. XHigh 1.5 MP generation is already available but is not this feature.
- [ ] Additional selectable open-weight video backends through a common take contract; model availability in ComfyUI alone is not Studio integration.
- [ ] Optional conversational orchestration after the individual functions and recovery controls are reliable.

## Distribution and operational limits

- [ ] Clean-install reproduction, versioned release packaging and authorized demonstration assets.
- [ ] Confirm repository publication and any submission acknowledgment separately; local exports are not publication or contest acceptance.
- [ ] Resolve model/dependency authorization and provenance questions using [LICENSES.md](../LICENSES.md), [submission readiness](submission-readiness.md) and the pack's [license inventory](../../LICENSES.md).
- [ ] Remote execution needs artifact transfer rather than shared local files. Changing the SDK URL alone does not provide a cloud deployment.
- [ ] Public deployment needs authentication, quotas and a deployment review. The maintained server is for a local user.
- [ ] Project ZIP import remains to implement/test; export and active-take management already exist.

Technical take checks detect some failed frames, not semantic correctness of faces, hands, labels, speech or narrative. Some source transitions are approximations. Text rendering is not automatic ASR, and timed dialogue is not yet a continuous narrator pipeline. Automatic pre-generation of scene illustrations and a second graphics engine were not adopted.

## Evidence and history

Use [changes.md](notes/changes.md), [audit corrections](notes/audit-fixes.md), [installation](installation.md) and the current README for maintained behavior. Recent local checks include 118 backend tests, a real procedural twenty-segment montage and six successful creative job exports; their scope does not certify every output. See the change log for skipped checks and targeted revalidation.

The old issue list and estimates are retained as [historical notes from 24–26 October](archive/known-issues-and-roadmap-2026-10-24.md). They are not current capability or schedule claims. Future checkboxes become complete only after relevant implementation and validation.
