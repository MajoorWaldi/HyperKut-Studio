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

Optional `-c constraints-release.txt` records a tested Studio dependency resolution. It is not a universal ComfyUI environment; install it only in the Studio virtual environment. See [validation scope](validation-summary.md).

Before the first Studio start, a rights-cleared [preset input bundle](portable-presets.md) can populate a fresh workspace. Upload IDs from the author's private installation alone are not portable. Launcher settings are machine-local and excluded from source control.

## 4. Start

Start ComfyUI first. From the Studio root:

```powershell
.\scripts\run_studio.ps1
```

The launcher uses ComfyUI on 8188 and Studio on 8090. `start_hyperkut.ps1` prefers the configured proxy port (8189) and automatically picks a free local port if that port is occupied by another service. A healthy proxy is reused only when its reported ComfyUI target and process-configured upload ceiling can both be verified and match; a healthy Studio is reused only when its non-secret configuration identity (hashed target/proxy/workspace plus storage backend) matches. Older services that do not expose enough identity are refused, not stopped or replaced; select another proxy port or stop them intentionally yourself. `run_studio.ps1` automatically selects a free local proxy port unless `-ProxyPort` is specified and applies the same proxy checks.

The Studio accepts browser media uploads up to **1 GiB**. Project transport permits **2 GiB per artifact blob** and **20 GiB total cached artifact bytes**; the bounded snapshot ZIP transfer limit is 20 GiB plus 32 MiB for descriptors and ZIP metadata. Both launchers therefore configure the SDK proxy to **20,512 MiB** per request. These are separate ceilings: the larger proxy allowance is for an already-preflighted snapshot bundle, not a way to bypass the Studio's 1 GiB media-upload limit. The current effective identity and limits are available at `GET /api/studio/status`.

Project ZIP import is limited by the workspace budget rather than the ordinary 1 GiB media-upload ceiling. It preflights expanded project size, copied input media, workspace budget and free disk before publication. Keep enough temporary space for the archive and its extracted project while importing.

Open http://127.0.0.1:8090/ . To select ports explicitly and use a nonstandard output folder already present on disk:

```powershell
.\scripts\run_studio.ps1 -ComfyUI http://127.0.0.1:8188 -ProxyPort 8189 -Port 8090 -OutputDir 'D:\ComfyOutputs'
```

ComfyUI and Studio must share the media/output disk. Changing the SDK endpoint alone is not cloud-deployment support. Retain the localhost binding unless access control and quotas have separately been implemented. This is not an installation of a hosted inference API.

Restart ComfyUI after engine/runtime changes only when no job is active; restart Studio for backend changes and rebuild the frontend for UI changes. Documentation-only updates require no restart. Validation tests and publication are separate, deferred release steps.
