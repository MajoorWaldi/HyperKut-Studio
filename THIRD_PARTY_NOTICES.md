# Studio third-party notices

The Studio's original code is MIT; preserve its [LICENSE](LICENSE). This is an acknowledgment index, not a license replacement or full transitive SBOM.

- Runtime Python dependencies are declared in requirements.txt. Preserve the licenses supplied by their exact installed distributions, including the official Comfy SDK and proxy, FastAPI, Uvicorn, HTTPX, Pydantic, filelock and python-multipart.
- React / React DOM are MIT; retain their notices when distributing compiled assets. Build/development tools keep their own licenses.
- Interface icon drawings are based on [Lucide](https://github.com/lucide-icons/lucide), ISC; retain the appropriate upstream copyright/permission notice when packaging these derived assets. The complete icon notice inventory remains a release-preparation item.
- The separate VideoTools renderer uses HyperFrames 0.8.201 (Apache-2.0), GSAP 3.15.0 (standard license), Tone.js 15.1.22 (MIT) and puppeteer-core 25.16.0 for Tone (Apache-2.0). Their licenses are not absorbed into the Studio's MIT license.
- The YuE2 instrumental helpers belong to the node pack and retain their own MIT notice. That notice does not cover model weights.

See [LICENSES.md](LICENSES.md), the pack's [third-party inventory](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools/blob/main/THIRD_PARTY_NOTICES.md), and each upstream license. Do not claim a distributable appliance or bundled environment is cleared until notices for all shipped binaries, fonts, models and assets have been reviewed.
