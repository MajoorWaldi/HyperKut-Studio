# Using HyperKut Studio

**Beta.** Finishing and AI extension candidates are experimental.

## Create an edit

1. Start ComfyUI and the Studio following [installation](installation.md).
2. Choose **Remix** for a reference edit, **Text** for an idea, or **Music** for a supplied track.
3. Add the required media and up to five image references. Describe each reference's role in the brief; a scene image is guidance, not a guaranteed first frame.
4. Choose format/quality and inspect the preset settings. Some presets intentionally differ from the new-project defaults.
5. Generate, review the planned shots and watch the result. Generation budget refers to requested footage, not wall-clock render time.

## Direct the idea

In **Artistic direction**, **Preview the creative brief** shows the enriched brief the planner will use, **Another idea** writes a different one for the same request (the plan, story and cast change), and **Three treatments** writes three at once: direct, with a twist, image-led. Choose one, edit it, then **Use this brief**. These steps prepare text only; nothing is generated.

Useful options (Options panel; all start off except where noted):

| Option | Mode | What it does | Cost |
|---|---|---|---|
| Casting | Text, Music | Story first, then a character, place and look for each shot; a voice file with no typed dialogue gets its lines shared between the shots. | One more planner call. |
| Kinetic lyrics | Music | Writes the words of the music on screen one at a time, a bigger one on the beats. Needs a voice in the music, the transcription (faster-whisper) and the HyperFrames finishing. | Finishing render. |
| Best of two takes | Text, Music | Two takes per shot with two seeds; a local vision model keeps one. | The shots stage takes about twice as long. |
| Pika H3 Flex | Text, Music | Six steps with the Flex LoRA instead of the turbo LoRA; another look, faster. Needs the LoRA file. | None. |
| Retry bad takes (on) | Text, Music | A black or noise-only take is made again with another seed. | One more take when needed. |

## Refine a shot

Select its timeline card, inspect the take/prompt and provide a correction. Regeneration creates another take for that shot; other shots retain their active takes. Select the take you prefer and re-edit/export to update the assembled video.

The source-window control selects which passage of a longer take is used. It changes the selected passage without changing that occurrence's cut length. Manual montage supports trim/slip and more general editorial changes.

## Manual montage

Open **Manual montage** to use the shared Timeline Edit editor. Cut, trim/slip, reorder, duplicate and select takes, with waveform, playhead and undo/redo. Saving the montage records a separate editorial document; exporting uses ComfyUI and keeps source takes. Preview source switches can pause; review the encoded export.

## Experimental finishing

Internal cuts, effects, text/titles, motion graphics, animated design, sound design and SFX start off. Enable only what the edit needs. HyperFrames/GSAP render requested graphic layers; Tone supplies a prebuilt optional cue bank. A subject mask is needed only for subject-dependent layers, not ordinary text.

Changing finishing can reuse existing footage, but still requires local assembly/rendering. If manual montage is active, use its export path; automatic re-edit and manual montage are separate editorial modes.

## Projects, presets and controls

Library opens on Projects, with Presets in a separate tab. Export a project ZIP from its video preview, then use **Import project ZIP** in the Projects tab on another Studio installation. Import validates archive paths, the saved shot manifest, timeline, media references and uploaded inputs; it assigns new project/upload IDs rather than trusting IDs in the archive. Imports require a shared ComfyUI output directory and available workspace/disk budget. Presets include settings and any inputs available on this installation; a private upload identifier is not a portable input. See [portable presets](portable-presets.md).

Stop cancels the current operation. Restart Studio restarts the web application, not ComfyUI; wait for active generations first. Keep the app bound to localhost.

Project ZIP archives are limited by the workspace budget (20 GiB by default); their expanded project and copied inputs must also fit the workspace and free-disk budgets while the archive is staged. Ordinary browser media uploads remain limited to 1 GiB by default. Voice/dialogue, graphic layers, location plates and experimental extension have additional model/runtime requirements. See [dependencies](dependency-scopes.md) and [known limits](known-issues-and-roadmap.md).
