# Studio installation and runtime scope

Documentation updated 2026-10-26. Fresh-clone and cross-platform validation are pending; this page is not a new installation-test result.

## 1. Engine and models

Use a recent ComfyUI with native H3, YuE2, Gemma, FLUX and BiRefNet support. Install Majoor VideoTools and comfyui_controlnet_aux for the maintained exported Studio API graphs. KJNodes and Easy-Use are additional dependencies of visual editor graphs. Download weights to the directories in the pack's [model inventory](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools/blob/main/docs/models-and-downloads.md); in a nested installation, [the local inventory](../../docs/models-and-downloads.md) is authoritative for this checkout. Read [licenses](../LICENSES.md) before using restricted weights. Some upstream downloads require accounts or accepted terms.

## 2. Graphics and sound finishing

In the **VideoTools pack root**, not the Studio folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_hyperframes.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\install_tone.ps1
```

Node.js 22+, npm, FFmpeg/ffprobe and a suitable local browser are required by these capabilities. Animated design, text, effects, sound design and internal sub-cuts are off by default. HyperFrames is needed when animated design or shared graphic layers are explicitly enabled. Tone's installer synthesizes the 30-cue bank once; mixing the bank does not launch a browser on every edit. Sound effects keep the existing toggle and the legacy fallback when no Tone bank is installed. No packages are installed during a generation request. Full runtime details: [pack guide](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools/blob/main/docs/install-finishing.md) / [nested local guide](../../docs/install-finishing.md).

## 3. Studio Python and frontend

In the **Studio root** on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Push-Location frontend
npm ci
npm run build
Pop-Location
```

The engine and Studio use separate Python environments. Do not replace ComfyUI's packages with the Studio's requirements-tested.txt snapshot. An already built frontend/dist needs no Node process to serve its assets, but this does not remove the Node requirement of HyperFrames or palette installation.

For the Windows/Python 3.14 release-validation dependency resolution captured on 2026-10-28, add `-c constraints-release.txt` to the pip command. Constraints pin versions without installing optional test tools unless they are requested. This captured environment passed startup, media and frontend checks; the backend suite now passes 220 tests with 6 skipped, but this is not a claim of a GPU installation test or a clone of the future published repository. Do not install these constraints into ComfyUI's own environment.

Before the first Studio start, a rights-cleared [preset input bundle](portable-presets.md) can populate a fresh workspace. Upload IDs from the author's private installation alone are not portable. The generic launcher settings example is intended for a new install; do not distribute the author's absolute output directory or Windows shortcut target.

## 4. Start

Start ComfyUI first. From the Studio root:

```powershell
.\scripts\run_studio.ps1
```

The existing launcher starts the SDK proxy on 8189 and Studio on 8090, using ComfyUI on 8188. Open http://127.0.0.1:8090/ . For a nonstandard output folder already present on disk:

```powershell
.\scripts\run_studio.ps1 -ComfyUI http://127.0.0.1:8188 -ProxyPort 8189 -Port 8090 -OutputDir 'D:\ComfyOutputs'
```

ComfyUI and Studio must share the media/output disk. Changing the SDK endpoint alone is not cloud-deployment support. Retain the localhost binding unless access control and quotas have separately been implemented. This is not an installation of a hosted inference API.

Restart ComfyUI after engine/runtime changes only when no job is active; restart Studio for backend changes and rebuild the frontend for UI changes. Documentation-only updates require no restart. Validation tests and publication are separate, deferred release steps.
