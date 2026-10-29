# Using HyperKut Studio

**Beta.** Finishing and AI extension candidates are experimental.

## Create an edit

1. Start ComfyUI and the Studio following [installation](installation.md).
2. Choose **Remix** for a reference edit, **Text** for an idea, or **Music** for a supplied track.
3. Add the required media and up to five image references. Describe each reference's role in the brief; a scene image is guidance, not a guaranteed first frame.
4. Choose format/quality and inspect the preset settings. Some presets intentionally differ from the new-project defaults.
5. Generate, review the planned shots and watch the result. Generation budget refers to requested footage, not wall-clock render time.

## Refine a shot

Select its timeline card, inspect the take/prompt and provide a correction. Regeneration creates another take for that shot; other shots retain their active takes. Select the take you prefer and re-edit/export to update the assembled video.

The source-window control selects which passage of a longer take is used. It changes the selected passage without changing that occurrence's cut length. Manual montage supports trim/slip and more general editorial changes.

## Manual montage

Open **Manual montage** to use the shared Timeline Edit editor. Cut, trim/slip, reorder, duplicate and select takes, with waveform, playhead and undo/redo. Saving the montage records a separate editorial document; exporting uses ComfyUI and keeps source takes. Preview source switches can pause; review the encoded export.

## Experimental finishing

Internal cuts, effects, text/titles, motion graphics, animated design, sound design and SFX start off. Enable only what the edit needs. HyperFrames/GSAP render requested graphic layers; Tone supplies a prebuilt optional cue bank. A subject mask is needed only for subject-dependent layers, not ordinary text.

Changing finishing can reuse existing footage, but still requires local assembly/rendering. If manual montage is active, use its export path; automatic re-edit and manual montage are separate editorial modes.

## Projects, presets and controls

Library opens on Projects, with Presets in a separate tab. Presets include settings and any inputs available on this installation; a private upload identifier is not a portable input. See [portable presets](portable-presets.md).

Stop cancels the current operation. Restart Studio restarts the web application, not ComfyUI; wait for active generations first. Keep the app bound to localhost.

Project ZIP export is available; ZIP import is not. Voice/dialogue, graphic layers, location plates and experimental extension have additional model/runtime requirements. See [dependencies](dependency-scopes.md) and [known limits](known-issues-and-roadmap.md).
