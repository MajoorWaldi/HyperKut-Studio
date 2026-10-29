# Runtime, development and optional dependencies

## Studio runtime

Install `requirements.txt`: comfy-sdk[pil], comfy-api-proxy, FastAPI, Uvicorn, python-multipart, HTTPX, Pydantic and filelock. Transitive packages such as PyYAML, aiohttp, blake3 and Starlette remain necessary to their parent packages. Use the existing ComfyUI Python for the engine and the separate Studio virtual environment for its web server.

An already built `frontend/dist` needs no Node.js process solely to serve its files. The complete app still needs Node.js for requested HyperFrames rendering and for explicit Tone palette installation. React is bundled in the assets. Keep the source/dev tools for future updates; do not strip them from a development installation.

## Development

`pip install -r requirements-dev.txt` includes runtime dependencies plus pytest and pytest-asyncio. Frontend `npm ci` installs TypeScript, Vite, Vitest, jsdom, Testing Library and oxlint. `requirements-tested.txt` is a historical full test-environment snapshot, including transitive packages and test tools; it is not the minimum production manifest.

## Workflow/model capabilities

Studio graphs: this pack + comfyui_controlnet_aux + native ComfyUI H3, YuE2, Gemma, FLUX and BiRefNet nodes. Visual workflow editing also uses KJNodes and easy-use. YuE2 uses one combined checkpoint. FLUX/Qwen4B/VAE, BiRefNet and DWPose/ControlNet serve retained optional functions; do not remove them just because a preset disables that function.

## Shared environment: verified limits

The current ComfyUI environment has opencv-python, opencv-python-headless and opencv-contrib-python 4.13.0.92. Installed packages request both ordinary OpenCV (including scenedetect, ultralytics, groundingdino and transparent-background) and headless (controlnet_aux, albumentations). CrossViewWarp imports contrib functionality. Removing any provider in place can break another extension or remove shared `cv2` files. No provider has been uninstalled. Consolidation requires an isolated environment or coordinated dependency changes across these packages, followed by reinstallation and tests.

Old music weights may be shared with personal workflows or experimental recipes. They remain installed. The maintained SECATOR workflows no longer need ACE-Step weights after the YuE2 migration; use the generated legacy-reference inventory before archiving shared models. No user media, project history, listening comparison or downloaded model was deleted or moved.

## Finishing runtime and licenses

HyperFrames 0.8.201 + GSAP 3.15.0 are installed separately in the VideoTools runtime; Tone.js 15.1.22 + puppeteer-core 25.16.0 produce the sound bank during explicit setup. HyperFrames and puppeteer-core are Apache-2.0; Tone.js is MIT; GSAP has separate standard terms. The Studio's graphics path needs HyperFrames when requested; animated design and finishing switches start disabled. Tone mixing reads prebuilt WAVs. See [installation](installation.md) and [license scope](../LICENSES.md). Missing required graphics dependencies fail explicitly; no automatic npm installation occurs during a generation.
