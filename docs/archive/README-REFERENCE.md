> Archived detailed reference, preserved 29 October 2026. For current setup, defaults and dependency scope, use [README](../../README.md) and [installation](../installation.md). Older default-enabled graphics descriptions below are superseded; finishing now starts disabled.

# HyperKut · HK

**An open-source local AI video studio.** Give it a reference edit and your own subjects, or an idea, or a piece of music: it makes the video, shot by shot, on your own GPU with locally downloaded models under their respective terms. Built on [ComfyUI](https://github.com/Comfy-Org/ComfyUI) for the [Open Source Higgsfield](https://comfy.org/open-source-higgsfield) challenge.

> Not affiliated with Higgsfield. "Katana" is their product; this is an independent open-source alternative that follows the same idea (recreate a reference edit with your subjects).

The [Katana improvement notes](../notes/katana-implementation.md) describe plate checks, local shot sources, editing-style references, energy/audio diagnostics and frame review. See [submission readiness](../submission-readiness.md) for the remaining publication and model-license questions. Identity, clothing, dialogue and voice still require human review of each result.

| Mode | You give | You get |
|---|---|---|
| **REMIX** | a video (the template of the edit), up to 5 pictures of your subjects, a sentence | a new rendering with your subject, using the reference cuts and measured rhythm/effects; camera and subject fidelity depend on generation and need review |
| **TEXT** | an idea, up to 5 pictures | a soundtrack made for it; the planner decides the cuts from your idea and the style, and the editor aligns planned cuts to its detected rhythm |
| **MUSIC** | your music, an idea, up to 5 pictures | adaptive or seeded-random musical editing, a regular beat/bar grid, or free narrative timing |

Shots are made by **MiniMax H3**; the plans are written by **Gemma 4**; new music by **YuE2**. The maintained generation path runs locally through the Comfy SDK and local proxy. Some model downloads and licenses require an account or authorization; see [licenses](../../LICENSES.md).

## Status

Reviewed **27 October 2026**. See the [current roadmap and known limits](../known-issues-and-roadmap.md) and the pack's [full capability checklist](../../../ROADMAP.md). A feature being available does not guarantee artistic quality, exact identity or correct action in every take.

What exists today:

- the web studio (React, English by default, French in the menu) and its server (FastAPI) that drives ComfyUI through the **official Comfy SDK** (`comfy-sdk`, with `comfy-api-proxy`);
- the three modes (Remix, Text, Music): the workflows are exported to API prompts in `workflows/`, run in three stages (plan, one prompt per shot, edit);
- per shot: thumbnail, prompt edit, **regenerate** (new seed, the other shots keep their take), take selection and retained versions; locking remains available through timeline controls, with its button removed from the shot prompt panel;
- user preset saving/import, voice sample and timed dialogue, reference video, folded optional controls, optional subject masks, unified HyperFrames graphics and Tone.js sound effects;
- a simulation mode (`SECATOR_MOCK=1`) to try the screens without a GPU;
- the nodes that do the work live in [ComfyUI-Majoor-VideoTools](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools) (MIT).

Tests: `pytest` (backend) and `npm test` in `frontend/`.

For release packaging, see [portable preset inputs](../portable-presets.md) and the [GSAP usage review](../notes/gsap-license-review.md). Private workspace upload IDs are not portable; use the explicit rights-gated bundle installer on a fresh installation. Source code and media have separate permissions.

Selected music and voice uploads display their measured waveform in the audio
picker before generation. Replacing or clearing the upload updates the preview;
decoding failures are shown in the picker without discarding the selected file.

### Music editing rhythm

In **Advanced options → Music & sound**, new **Text** and **Music** Studio requests,
and **Remix → New sound**, default to **Adaptive musical**.
Remix with original audio or voice keeps its reference editing behavior.
Quiet passages get longer holds; energy, changes in local
energy and measured kick/snare accents guide tighter passages. The optional
artistic mood biases pacing; energy alone does not identify emotion or musical genre.
**Random musical** varies intervals reproducibly using the job's seed.
**Regular** exposes the existing beat/bar interval. **Free** leaves narrative
durations to the planner, with no automatic beat snapping or density burst.

Cut pace changes the target interval; duration variation changes its spread.
With a detected pulse and nonzero variation, adaptive/random also mix musical
phrases: longer holds followed by one/two-beat cuts and paired half-beat bursts.
Adaptive reserves these phrases for sufficiently active passages. Variation zero
disables phrases. The minimum shot length is five frames (about a half beat at
144 BPM and 24 fps); faster half beats are limited by that minimum.
This is an editing minimum, not a five-frame model generation request: the
MiniMax profile keeps its existing generation length and 17k+5 alignment.
Musical synchronization favors nearby measured accents and beats, rather than
requiring every beat. With no reliable accents, adaptive/random use varied
narrative timing and report a warning. A seeded result is reproducible for the
same audio, settings and planner output; LLM prompts themselves are not guaranteed
deterministic.

Adaptive/random/regular apply actual integer-frame timing after planning.
Generated take count, ids and prompts are preserved. Additional cuts reuse
excerpts of the same take, matching planned sub-cut effects where supplied or
using jump-cut source windows otherwise; they do not automatically buy another
generation. Continuous/protected actions keep their internal hold. A requested
take count greater than the selected intervals requires extra take boundaries,
which is reported. Therefore cut pace is a target, not a promise of an exact
cut count. As with existing plans, **Effects off** or disabling sub-cuts in
Edit style suppresses those internal cuts; generated-take boundaries remain.

Existing saved requests without these settings retain **Legacy project**
behavior. Presets save the new controls; new preset selections without a rhythm
mode inherit the Studio default. Changes affect subsequent analysis, not existing
generation plans, saved raw takes or the manual montage.

Text applies the selected policy after the generated soundtrack is available,
instead of the old half-beat snap and automatic burst. Remix with New sound
applies musical excerpt cuts at export inside generated takes while preserving
the reference shot boundaries, shot count and duration. Original retained takes
and protected continuous actions are not interrupted. Remix never overwrites
the generation manifest or raw takes; Effects/sub-cuts off suppress internal cuts.

After updating, restart Studio **and ComfyUI** to load the node's new optional
inputs. Studio checks the live node schema before submitting a musical-policy
workflow and reports a restart requirement rather than silently ignoring the mode.

Remix retains the exact H3 prompt with each new generated take, including the
judge's correction when a retry is selected. The shot panel displays this prompt
read-only for the take being previewed. Use the separate correction field to
direct the next take; the generated prompt is never fed back as a user correction.
Older takes have no recorded generation prompt and cannot be reconstructed
exactly. Shots retained from the source also have no generation prompt.

### Experimental AI edit candidates

Set `SECATOR_EXPERIMENTAL_AI_EDIT=1` in the backend environment to expose a separate
extension controls on generated source shots. The existing **Regenerate**
action remains the only regeneration button. **Extend** adds Before/After and
additional seconds, reusing the shot prompt above without a second prompt field
or source-video preview. Remix combines the recorded take prompt with the current
correction; Text/Music use the current editable shot prompt.
Extension uses the native H3 boundary-image guide. Review the
candidate video, then explicitly accept or reject it. Until acceptance, the
active take, manifest and existing export stay unchanged. Acceptance retains
previous takes; use **Edit style → Re-edit** to update the export afterwards.

This is **source-shot scope**, not per-occurrence timeline editing. It uses the
configured text H3 sampler and up to five image references, without Remix pose
guidance, voice conditioning or finishing effects. Generation is 24 fps with a
124-frame minimum; extension adds 0.25–10 seconds, and generated segments are
limited to 362 frames. Music/overlays are not automatically retimed. Existing
Timeline Edit documents are not automatically rebased when new takes are added.
H3 visual/audio continuity and a complete model-backed export are **not yet
qualified**. The feature is off by default and requires the real SDK runner,
proxy and models; mock mode does not pretend to generate candidates.

See the pack's [implementation checklist](../../../docs/timeline-edit-implementation.md#prototype-studio--candidates-ia-avant-validation-complete)
for tested contracts and remaining validation gates.

### Manual post-generation montage

Open **Manual montage → Open Timeline Edit** on a generated project. This is the
same editor as the adjacent VideoTools node, not a second implementation:
left/right trim handles and numeric trim, slip, cut at cursor, drag/reorder,
ripple delete, duplicate, occurrence-local take replacement, undo/redo, music
waveform, seek/frame stepping and play/pause.
The selected occurrence has a source filmstrip with a highlighted window:
drag either edge to ripple trim, or drag the window to slip without changing
the clip length. Filmstrip and timeline handles stay synchronized; each drag
is one undoable edit, and cancellation restores the previous window.
Arrow keys adjust one frame. Exact In/Out and slip inputs remain under
**Frame controls**. Thumbnails decode locally in a separate, bounded player;
they never seek the playback preview or modify source takes.
Studio applies its own scoped plum/lavender/lime skin to the shared editor,
including transport, trim handles, waveform, inspector and save/export states.
The ComfyUI node keeps its existing default appearance.

**Save montage** writes a separate `editor/timeline.json`; it never rewrites the
generation manifest or existing video. **Save and export** runs the actual Comfy
Timeline Edit/Assemble graph through the SDK. It preserves the previous export
on failure. Update/restart ComfyUI to register `MajoorTimelineEdit` before exporting.
The Studio must remain adjacent to its VideoTools pack.

The editor retains a browser draft and refuses concurrent-version overwrites.
Download the JSON before discarding a conflicting draft or resetting. Source
changes require explicit **Rebase unchanged takes**; this preserves every clip
identity, chosen take, window and order, and refuses changed referenced media.
Cleanup retains even inactive takes used by the saved montage.
Disable manual mode to apply automatic edit styles; its document remains saved.
The source-shot strip is not the exported occurrence timeline, so result-following
and timestamp-based Remix comparison are disabled for manual exports.

This is a sequential, raw-take montage: automatic effects, text, motion layers
and sub-cuts are not reapplied. Music starts at zero (retained soundtrack, source
music, or Remix source audio). **Dialogue from selected take** adds a waveform
excerpt, initially source-aligned, retaining available audio beyond the picture
cut. Drag it for J/L cuts, trim its own handles, or set exact position/In/Out and
volume (zero mutes); delete and undo/redo also support dialogue. Video edits do
not move or duplicate these independent excerpts. Overlapping audio is mixed.
**Music volume** is saved and shared by preview/export; no automatic ducking or
audio effects are added to manual exports. Explicit dialogue replaces cut-linked
take audio and remains audible when music is present. It may include ambience:
this is not voice isolation.
If Remix uses the original source soundtrack as its fallback music, adding an
explicit dialogue track replaces that fallback instead of replaying the same
voices underneath themselves. Actual retained/replacement music remains mixed.

An audible dialogue excerpt beyond the picture blocks export rather than silently
truncating a sentence. Extend the picture, move/trim the excerpt explicitly, or
mute it. Existing documents without a dialogue array retain their previous
behavior: music mutes take audio on export; without music, export keeps take
audio although browser preview mutes it. Adding dialogue is explicit, never a
destructive migration of saved edits. Rebase and take cleanup protect audio-only
references too. Missing speech in the raw take cannot be reconstructed.

For new automatic plans requesting dialogue/voice, musical retiming gives way to
narrative timing. Full timed lines are kept instead of clamped to shot ends.
Voice-shot assembly uses a continuous independent take-audio bus and omits
internal cuts/speed effects; an overlong tail requires an explicit edit.
Restart **both Studio and ComfyUI** after this update. Studio rejects an old live
assembler before submitting model generation for a dialogue request.

Proxy preloading/gapless playback, music trim, multiple video layers and effect
retiming are not implemented. A hidden browser tab may suspend media playback;
decoding/playback errors are shown, never hidden as success.
Opening the editor pauses the Studio preview and shot players; background
autoplay stays paused while the editor is open. Closing does not restart them
automatically. Playback waits for music seeks and video readiness before
starting music, supports cancellation during startup, and reports a timeout
if a media wait/start exceeds 15 seconds. Rapid Play/Pause/Play and cancelled
trim gestures do not leave a stale loading state or stop a newer request.

AI candidate actions remain source-shot scoped. After accepting a candidate,
explicitly rebase, reopen the editor and select that take on the desired
occurrence. No model is called by trimming, cutting, saving or rendering a manual
montage. Real isolated SDK/Comfy exports have been verified with synthetic media;
this is not a qualification of H3 continuity.

### What works, what remains

| Capability | Status |
|---|---|
| Multi-shot creation, hooks, product ads and short stories | Implemented; narrative continuity, identity and action fidelity still need review. |
| Remix, music-driven edits, shot regeneration and re-editing | Implemented. Current Music planning uses a candidate grid rather than a fixed take count. |
| Five image-reference inputs | Implemented. An image can guide identity, product, style or scene; specify its role in the prompt. Automatic role assignment is not implemented. |
| H3 shot audio, YuE2 music and synthesized SFX | Implemented; musical phrasing and sync quality remain improvement targets. |
| Animated typography, vector/effect layers and masks | Implemented via HyperFrames. Style layer packs, subject-derived accents and dedicated numeric counters remain unfinished. |
| UGC dialogue, faceless videos and infographics | Partial: useful building blocks exist, without complete specialized authoring/validation flows. |
| Continuous narrator audio and script-driven scene timing | Planned; per-shot H3 dialogue is not a complete continuous-narration pipeline. |
| Speech transcription and word-aligned subtitles | Planned; animated text and reading existing visual overlays do not transcribe speech. |
| YouTube/long-video semantic highlight selection | Planned; scene detection and Remix are already available but do not select the most meaningful passage. |
| Voice-preserving dubbing/translation | Planned. The EN/FR interface is already available and is separate from audio localization. |
| Automatic finished-video reframing | Planned; generation ratios and manual edit crops already exist. |
| Product-URL/brand research, selectable video backends, 4K upscale and agent chat | Planned, not current Studio functions. H3 is the maintained video backend. |

Recent updates distinguish generated takes from editorial cuts, allow explicit requests for many short plans, scope the H3 writer to its own shot, preserve set dressing in location plates, and improve word timing/readability. A CPU check assembled twenty segments into fifteen seconds, including three-frame inserts; this is not a full H3 creative benchmark. The standard H3 workflow retains a 124-frame minimum per take.

Quality controls: Draft ~0.35 MP (often called 0.4 MP), Standard 0.6 MP, Max ~0.98 MP and XHigh 1.5 MP. XHigh increases generation size; it is not a 4K upscaler.

Creative controls: Text/Music expose three named levels for **Reference fidelity** and **Creative freedom**, applied to both enrichment and planning. Fidelity concerns reference composition/treatment while identity and product design remain preserved. It is disabled until a visual reference is supplied. Remix instead exposes actual **Motion guidance** strength (0.40–1.00), retaining the previous pose behavior rather than claiming a 0–100% fidelity score. These controls apply to new jobs; regenerating a take uses its original project's settings. Changing a creative level preserves an edited brief, which can be explicitly reused with current settings without another model call. Legacy numeric settings and matching legacy brief contexts remain readable.

The previous bundled and saved presets were deliberately removed. Six new creative auditions have local exports; artistic selection and creating new localized presets/demo media remain pending. The existing preset feature remains usable. Automatic scene-illustration pre-generation was tested and set aside; it is not enabled in the maintained pipeline.

For normal use install `requirements.txt`. For development install `requirements-dev.txt`. `requirements-tested.txt` is a full Windows/Python 3.14 test-environment snapshot, not the minimal runtime dependency list. See [the audit corrections](../notes/audit-fixes.md) for behavioral changes and remaining limits.

What is not done or not tested, how to fix it, and what comes next: [docs/known-issues-and-roadmap.md](../known-issues-and-roadmap.md).

## Install

You need a working ComfyUI with the node packs below, Python 3.10+ and Node.js 22+ for frontend builds and graphics rendering/palette installation, plus FFmpeg/ffprobe and a suitable local browser for finishing.

1. For the exported Studio API workflows, install **ComfyUI-Majoor-VideoTools** and **comfyui_controlnet_aux** in `ComfyUI/custom_nodes/`, with a recent ComfyUI supporting native H3 and YuE2 nodes. **KJNodes** and **comfyui-easy-use** are additionally required to open/edit the visual workflows, but are not used by the exported Studio API graphs. Models are listed in the `DEPENDENCIES` note of each workflow.
2. From the **VideoTools pack root**, install graphics and the synthesized sound palette:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\install_hyperframes.ps1
   powershell -ExecutionPolicy Bypass -File .\scripts\install_tone.ps1
   ```
   Animated design is enabled by default. Requested text/layers also need the shared renderer. See [installation](../installation.md) and [dependency scope](../dependency-scopes.md). Then, in the **Studio root**:
   ```bash
   python -m venv .venv
   .venv/Scripts/pip install -r requirements.txt        # Windows; on Linux and macOS: .venv/bin/pip
   # Only when frontend/dist is absent or after changing the frontend:
   cd frontend && npm ci && npm run build && cd ..
   ```
3. Start ComfyUI, then the proxy that gives the SDK its API, then the studio:
   ```bash
   .venv/Scripts/comfy-api-proxy start --comfyui http://127.0.0.1:8188 --port 8189
   .venv/Scripts/python -m uvicorn backend.server:create_app --factory --host 127.0.0.1 --port 8090
   ```
   (`.\scripts\run_studio.ps1` does both, from any working directory.) Open <http://127.0.0.1:8090>.

When the studio is nested in this node pack, it also discovers the standard ComfyUI output folder. For a standalone studio or a nonstandard output folder, set the absolute `SECATOR_OUTPUT_DIR` (or pass `-OutputDir` to the launcher). The studio and ComfyUI must share this disk; changing the SDK URL alone does not enable a remote/cloud deployment.

The launcher also accepts `-ComfyUI`, `-ProxyPort` and `-Port`. Click the connection indicator to refresh the proxy, nodes and model diagnostics. Rebuild the frontend and restart both ComfyUI and the studio after updating this pack.

Each new job forks its own project from the reusable plan/detection. Older projects shared by several jobs are protected from editing and file deletion: start a new generation to obtain an independent project. Prompt, active-take and purge changes use the same project lock as ComfyUI and save manifest history atomically.

Uploads are streamed and decoded before submission. Default limits are 1024 MB per file, 3600 seconds and 4096×4096 pixels; configure `SECATOR_MAX_UPLOAD_MB`, `SECATOR_MAX_MEDIA_SECONDS` and `SECATOR_MAX_MEDIA_PIXELS` to suit your machine. `SECATOR_MAX_ACTIVE_JOBS` defaults to 8. Music mode requires a track; voice mode requires a sample and timed dialogue; references are limited to the five slots the app actually wires.

The generation budget counts footage requested from H3, including a possible retry; it is not a render-time estimate. The on-grid metric uses independent measured music times and is hidden for older projects without them. The cheap Take Check detects technical failures only, not identity, hands, text or lip-sync. Some transitions are approximations (for example, crossfade is rendered as a blur), not exact reconstructions of a reference.

The server is intended for one local user. Keep its localhost binding. Public deployments require access control and resource quotas at a trusted reverse proxy before exposing the API, including its upload and deletion routes.

Uploads use safe media extensions and response types. Existing images with unusual filenames remain readable; files that cannot be identified safely are served as downloads. The local API checks Host and mutation Origin headers. `SECATOR_ALLOWED_HOSTS` can explicitly name additional hosts when needed; this does not add authentication or make a public deployment safe.

Project ZIP exports include referenced project media, retained music and uploaded inputs. `request_files.json` maps the input IDs in `request.json` to files inside the archive. Missing referenced files produce an error instead of an incomplete backup. Models and installed runtimes are not included, and the Studio does not yet offer a ZIP import command.

New submissions retain their SDK request ID while running. After an interrupted Studio session, startup reconciles/cancels that request rather than automatically restarting generation. If the local proxy is unavailable, mutations retry reconciliation once the connection is restored. Existing jobs from before this update have no saved request ID. The browser retries brief stream interruptions and rereads job state before reconnecting.

## Develop

Frontend development packages are not required to serve an already compiled `frontend/dist`. Node.js still runs HyperFrames when graphics are requested and builds the Tone palette during explicit installation. See [dependency scopes](../dependency-scopes.md).

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest          # the server
cd frontend && npm run dev              # the interface, with the server on port 8090
SECATOR_MOCK=1 .venv/Scripts/python -m uvicorn backend.server:create_app --factory --port 8090
```

## Rights of the videos and the music

The app makes new pictures, but a **Remix** follows the cuts, the camera and the rhythm of a reference video, and a **Music** edit follows a track. Both belong to someone.

- Use your own reference video, or one that is free to use. A viral video belongs to its author.
- Use music that you have the right to use. The tracks you add are yours; nothing is checked or kept by the app beyond your own computer.
- Pictures of a real person (your references) need that person's agreement.
- The licenses of the models (below) also apply to what they make.

The interface says it next to the video and music slots and on the first screen.

[Résumé des licences en français](../licences-resume.fr.md).

## Models and their licenses

The application code is MIT; this does not license weights, third-party dependencies or user media. H3 uses its own community/authorization terms; YuE2 uses model-specific terms with additional individual-creator permission. These are not universal commercial grants.

Read [LICENSES.md](../../LICENSES.md) for the current sources and unresolved items. The pack's [model inventory](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools/blob/main/docs/models-and-downloads.md) lists configured checkpoint filenames. Tone.js is MIT; HyperFrames and puppeteer-core are Apache-2.0; GSAP keeps its own standard license. Preserve [third-party notices](../../THIRD_PARTY_NOTICES.md).

## License

MIT for the original Studio source. See [LICENSE](../../LICENSE), [license scope](../../LICENSES.md) and [third-party notices](../../THIRD_PARTY_NOTICES.md).

The icons of the interface are drawn after [Lucide](https://lucide.dev) (ISC license).


### Very short Remix shots

The Studio pads H3 video references shorter than five frames by repeating their last frame. Only the reference is padded; the original shot duration and cut timing remain unchanged in the final assembly. Shots of five frames or more keep their full reference, and the existing no-subject and pose-only decisions are preserved. This is automatic and adds no UI controls. The template exporter retains this adaptation.

## Generated music: YuE2

The Studio uses the official ComfyUI YuE2 nodes and `models/checkpoints/yue2_3b_int8_convrot.safetensors` (Comfy-Org/YuE2), with full ABC planning and native 32-step synthesis. The approved audiovisual music brief remains in place. Text generates new music; Remix uses YuE2 only when its existing replacement/no-audio branch requires new music; Music mode keeps the supplied track. The exporter performs the same conversion when templates are rebuilt. No model selector is added.

Vocal textures use wordless vocalises unless lyrics are explicitly supplied to the native adapter; instrumental requests transfer vocal score notes to the instrumental part with the upstream MIT-licensed helpers in `core/vendor/yue2`. Strict audible absence of vocals still needs listening; the score conversion itself is validated. The duration output of the music encoder drives the latent; Music Fit adapts the result to the edit. BPM/key are intentions, not guaranteed measured properties.

Code, helper and model licenses are distinct; see [LICENSES.md](../../LICENSES.md). Source weights: https://huggingface.co/Comfy-Org/YuE2. The selected model alone does not establish competition eligibility.

## Optional artistic direction and brief preparation

The original SECATOR interface provides an optional, initially folded Artistic direction panel. All choices default to Automatic; the initial editing profile is now `none` rather than a fixed viral profile. Explicit existing presets remain available. A shared server-side vocabulary validates visual style, mood, camera and lighting and builds the direction used by the enhancer, planner, shot requests and music context. No cloud image generation or external studio code is used.

In Text and Music modes, Preview the creative brief runs only the local enrichment branch with the supplied references. It does not start music, video or a project. The user can edit the generated prose and select Use this brief, or generate directly from the original phrase as before. Prepared text uses the interface language. Remix retains its source cut timing and accepts the optional visual choices without a separate enrichment preview.

An accepted brief bypasses the enrichment LLM for that request; it is not silently rewritten before planning. Changes to the creative request or references invalidate acceptance. The server independently rejects stale accepted briefs; random seed changes alone do not invalidate them. The preview is serialized and refuses to start while generation is active. Tests cover stale rejection, shared creative context, automatic defaults, preview-only behavior and editable acceptance. Existing YuE2, media generation workflows, subject masking, timelines and local storage stay in place.

## Runtime dependency scope

See [dependency scopes](../dependency-scopes.md) for runtime/development separation, optional models and shared-environment cleanup limits. Uvicorn is installed without its optional `standard` extras; the launcher uses HTTP/SSE without automatic reload. Installing development extras later is optional. No code changes or removals are made to other custom nodes.

## Current finishing and publication scope

The three Studio modes use one HyperFrames compositor for typography/motion and the existing assembler for editing/audio. The 30-sound Tone palette includes real stereo transitions; the separate Sound effects switch controls it. Musical signatures are explicit cues, not added on every cut. Nine presets have English/French names, descriptions, editable prompts and musical/camera direction.

This README describes the working checkout, not a claim that both repositories or every change have been published. Check [submission readiness](../submission-readiness.md) before citing a release. Documentation-only changes do not require a restart.

## HyperKut naming and compatibility

The application is now **HyperKut**, with **HK** initials and a scissors mark. The installed directory `HyperKut Studio`, existing project paths and historical workflow filenames remain valid. New exports use `hyperkut_`. Use `HYPERKUT_*` environment variables; their corresponding `SECATOR_*` names remain accepted as compatibility aliases. When both are set, `HYPERKUT_*` takes priority. Browser language and zoom preferences retain their previous values.

## Windows launcher

Double-click **HyperKut Studio.lnk** in this folder (scissors icon). It reuses running services, starts the local Studio/proxy when needed, then opens your default browser. The fallback is `Lancer HyperKut.cmd`. ComfyUI remains a separate service for generation. Launcher configuration is in `scripts/launcher/settings.json`; logs are under `workspace/logs`.
