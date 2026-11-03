# Changelog

## Current beta

- Remix gets the creative tools of Text and Music. A remix planner (creative or transfer strategy, or casting on) reads the whole source and writes the story line of each shot, who of the pictures replaces whom, the places and the shots to keep as in the source or turn into a title card, without changing the cuts. Also: best of two takes judged against the source shot, visual memory of each person, location images, camera moves for a creative remix, transcription of the source for kinetic lyrics, three Remix treatments (faithful, twist, another story), and a "Keep the original shot" toggle per shot. An older ComfyUI without the Remix Plan node makes the remix without its plan.
- The storage lock no longer freezes the Studio during an upload check, an import or an export; Clean caches also removes unused uploads and the pictures the Studio cut.
- Text and Music: story then casting, voice and lyric transcription, visual memory, camera moves, Another idea, three treatments, best of two takes (the second take now has its own seed), kinetic lyrics and the Pika H3 Flex option; see the VideoTools changelog for the nodes. Missing optional models or nodes (Pika Flex LoRA, FLUX location images, pose control, music model) are cut out of the prompt instead of stopping a generation.

- CI uses a matching VideoTools runtime with motion templates and checks lazy-loaded motion modules before running backend tests.
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
