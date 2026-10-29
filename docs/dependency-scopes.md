# Dependency scopes

## Studio runtime

Install `requirements.txt` in a **Studio-specific Python virtual environment**. It declares comfy-sdk[pil], comfy-api-proxy, FastAPI, Uvicorn, python-multipart, HTTPX, Pydantic, filelock and AnyIO. Their transitive dependencies remain governed by their own packages.

ComfyUI uses its own environment for PyTorch, node packs and model loaders. Do not replace it with the Studio's dependency snapshot. Shared ComfyUI installations may have dependencies used by other node packs; do not uninstall them based only on a disabled Studio option.

## Frontend and development

React/React DOM are bundled by the TypeScript/Vite build. Node.js 22+ and npm build the frontend; an existing `frontend/dist` is served by FastAPI without a separate Node web server. `requirements-dev.txt` adds backend test tools. `requirements-tested.txt` and `constraints-release.txt` record a particular dependency resolution, not a universal engine environment.

## Generation

The maintained API graphs use Majoor VideoTools, comfyui_controlnet_aux and native ComfyUI model nodes. Visual workflow editing additionally uses KJNodes/Easy-Use. Gemma/H3 drive the maintained planning/video path; YuE2 creates new music. Location plates, pose processing and masks require the models of the selected branch. See the [model inventory](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools/blob/main/docs/models-and-downloads.md).

## Experimental finishing

| Component | Purpose |
|---|---|
| HyperFrames 0.8.201 + GSAP 3.15.0 | Requested graphic layers and animation; needs Node.js 22+, FFmpeg/ffprobe and a compatible browser. |
| Tone.js 15.1.22 + puppeteer-core 25.16.0 | One-time synthesis of the optional 30-cue bank using local Chrome/Edge. Mixing existing WAV cues does not launch a browser per edit. |

Finishing starts disabled. Missing requested runtimes produce an error; generation requests do not install npm packages automatically. Packages and fonts/browser resources should be provisioned before offline use.

[Installation](installation.md) · [License scope](../LICENSES.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)
