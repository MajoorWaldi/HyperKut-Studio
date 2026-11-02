# Beta status and known limits

HyperKut Studio is beta. The maintained [roadmap](../ROADMAP.md) lists implemented capabilities, experimental features and planned work.

| Area | Limit |
|---|---|
| Generated footage | Identity, clothing, product geometry, hands and action continuity depend on the model and inputs. Review each take. |
| Remix | Structure and timing guide generation; exact motion, camera and graphics preservation are not guaranteed. |
| Finishing | Effects, titles, motion graphics, sound design and SFX are experimental and start disabled. Preview and final rendering may need adjustment. |
| Audio | Measured accents guide editing; exact generated song structure, voice identity and lip sync are not guaranteed. |
| Narration/subtitles | Timed dialogue and animated titles are not a complete continuous-narrator pipeline. The words of a voice or song are transcribed with faster-whisper for prompts and kinetic lyrics; recognition errors reach the prompts and the generated speech. |
| Best of two takes | A local vision model picks the take; its choices are not measured against human review. It doubles the shots stage. |
| Lip sync | The mouth follows the voice partially; the lip sync check is not wired into the Studio graphs and its result was inconclusive on the clips tried. |
| Visual memory | Assumes the subject is near the centre of the frame; it keeps identity, not pose. |
| Pika H3 Flex | Speed gain seen on one run; quality is not qualified. |
| Manual montage | Source switching can pause during preview. Experimental extension requires explicit acceptance and a subsequent export; overlay/music timing needs review. |
| Portability | ZIP export exists; project ZIP import does not. Preset inputs must be installed or uploaded separately. |
| Deployment | Shared local media storage is expected. No qualified public multi-user hosting, automatic remote artifact transport or cross-platform GPU installation is claimed. |

[Installation](installation.md) · [User guide](usage.md) · [Licenses](../LICENSES.md)
