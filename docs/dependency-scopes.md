# Dependency scopes

## Studio runtime

Install `requirements.txt` in a **Studio-specific Python virtual environment**. It declares comfy-sdk[pil], comfy-api-proxy, FastAPI, Uvicorn, python-multipart, HTTPX, Pydantic, filelock and AnyIO. Their transitive dependencies remain governed by their own packages.

ComfyUI uses its own environment for PyTorch, node packs and model loaders. Do not replace it with the Studio's dependency snapshot. Shared ComfyUI installations may have dependencies used by other node packs; do not uninstall them based only on a disabled Studio option.

## Frontend and development

React/React DOM are bundled by the TypeScript/Vite build. Node.js 22+ and npm build the frontend; an existing `frontend/dist` is served by FastAPI without a separate Node web server. `requirements-dev.txt` adds backend test tools. `requirements-tested.txt` and `constraints-release.txt` record a particular dependency resolution, not a universal engine environment.

Studio's tests also use VideoTools' shared core schema, timeline editor and motion templates. Keep the Studio checkout directly inside a VideoTools checkout (for example `videotools/HyperKut Studio`); run Python tests from the Studio root and frontend tests from its `frontend` folder. Both CI jobs reproduce this layout with VideoTools pinned to commit `5badde870056894128198189cde88bc96adf2779`, which includes `core/motion_library.py` and the video model registry (`generators/`, `core/cost_guard.py`) that the Studio reads. Update both pins together when qualifying a newer shared runtime. The backend import check expands and validates a motion template to exercise the lazy-loaded shared modules before running the suite.

## Generation

The maintained API graphs use Majoor VideoTools, comfyui_controlnet_aux and native ComfyUI model nodes. Visual workflow editing additionally uses KJNodes/Easy-Use. Gemma/H3 drive the maintained planning/video path; YuE2 creates new music. Location plates, pose processing and masks require the models of the selected branch. See the [model inventory](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools/blob/main/docs/models-and-downloads.md).

Optional, in ComfyUI's Python and not in the Studio's: `faster-whisper` with the `large-v3` folder, read by Transcribe Voice to turn the words of a voice or a song into text with times (prompts, phrase cuts, kinetic lyrics). Without it the transcription is skipped and the edit goes on. The Pika H3 Flex LoRA (`pika_h3_flex_ref2va_v1_bf16.safetensors`, loras folder) is needed only by the Flex option. The best-of-two judge uses the Gemma vision model already listed; no extra file.

## Optional dependencies and what happens without them

| Optional dependency | What it adds | Without it |
|---|---|---|
| `faster-whisper` and the `large-v3` folder | The words of a voice or a song. | No words: the prompts have no lyrics, the cuts do not follow phrases, no kinetic lyrics. The edit goes on. |
| Pika H3 Flex LoRA | The Flex option (six steps). | The turbo LoRA is used; the user is told when the option was on. |
| MiniMax H3 Image files (`minimax_h3_image_pruned_int8_convrot`, `minimax_h3_image_vae_fp16`; the text encoder is the one of H3) | Images of the places of the shots. | The shots are made without them; the user is told when the option was on. |
| YuE2 music model | Music generated for a Text edit. | The edit is cut on a steady grid and has no generated music; the user is told. Music mode (your own track) never needs it. |
| `comfyui_controlnet_aux`, DWPose and YOLOX files, the H3 pose patch, the Marigold node | Pose control. | Not needed by Text and Music shots: they are made without it. Only a Remix that asks for pose only needs them. |
| HyperFrames (Node.js 22+, a browser) | Text, graphics, kinetic lyrics, effects. | The video is kept as assembled, with a warning. |
| Tone bank (`install_tone.ps1`) | Generated sound effects. | No generated effects, with a warning. |
| BiRefNet | Layers that need the subject cut out. | Those layers are skipped, with a warning. |
| KJNodes, Easy-Use | Editing the visual workflows by hand. | The Studio graphs do not use them. |

Required, and reported with a clear message when missing: ComfyUI with the native H3, Gemma and YuE2 nodes, Majoor VideoTools, the Gemma planner files, the H3 model, encoder, VAEs and turbo LoRA, FFmpeg. A missing optional dependency must never stop a generation or the final montage; if one ever does, it is a bug to report.

The Studio asks ComfyUI which files and nodes it has before it sends a shot or a plan, and cuts the branches of the missing ones out of the prompt. If ComfyUI cannot be asked, nothing is cut.

## Experimental finishing

| Component | Purpose |
|---|---|
| HyperFrames 0.8.201 + GSAP 3.15.0 | Requested graphic layers and animation; needs Node.js 22+, FFmpeg/ffprobe and a compatible browser. |
| Tone.js 15.1.22 + puppeteer-core 25.16.0 | One-time synthesis of the optional 30-cue bank using local Chrome/Edge. Mixing existing WAV cues does not launch a browser per edit. |

Finishing starts disabled. Missing requested runtimes produce an error; generation requests do not install npm packages automatically. Packages and fonts/browser resources should be provisioned before offline use.

[Installation](installation.md) · [License scope](../LICENSES.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)
