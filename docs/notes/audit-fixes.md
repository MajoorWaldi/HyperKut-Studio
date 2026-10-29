# Local reliability corrections — 24 October 2026

This update addresses the code defects identified in the SECATOR audit. It does not establish visual parity with Katana or predict social performance.

## Completed independent review and fidelity follow-up

The independent review completed after the initial partial pass. Project manifest locks now run outside the async event loop, with a reservation that prevents conflicting mutations while a thread waits. Audio/video uploads and finished outputs undergo actual FFmpeg decoding, with a 120-second validation limit; a valid metadata header alone is insufficient. Validation and ZIP cancellation wait for their worker to close files before temporary-file cleanup, including on Windows.

Remix regeneration now selects the original source shot rather than using the previous generated take as the next structural reference. This limits accumulated drift; keep all desired changes in the shot prompt. Reload the updated Remix graph for direct graph use. The writer gives a scoped shot correction priority over the global brief for the named attributes, repeats target attributes in subject and shot descriptions, and no longer labels a recolored reference as fully preserved.

A same-seed synthetic product test checks color across every frame; its actual submitted H3 prompt and before/after outputs are recorded in the separate follow-up report. This is an improvement on that tested case, not a general facial-identity, text/logo or arbitrary-scene guarantee.

- New jobs fork an independent project from the initial shot list. Source media can be hard linked because the app never edits those bytes in place. Legacy shared projects refuse mutations and project-file deletion until a new independent generation is made.
- Job JSON is saved atomically. A bounded Windows retry tolerates transient readers that temporarily deny replacement, in both the app and the project store. A corrupt saved job is reported in the connection diagnostic instead of preventing all other projects from opening. Project edits share ComfyUI's `.lock`, increment the revision and save a manifest snapshot.
- A result is downloaded to a temporary MP4 and checked with FFprobe before replacing the previous video. Missing output, malformed responses and other exceptions produce a failed state; cancellations remain distinct. Progress and preview state restart for each operation.
- The Remix shot correction is connected to the reader/writer brief. New API exports pass numeric shot start/duration for dialogue; existing graphs accept decimal time headers. Successful edit overrides are reused by later regeneration and montage. A failed re-edit restores the previous rendered style.
- Uploads are streamed, bounded and decoded. Modes validate the media roles they use. The five-reference limit is the capacity of this app's actual slots, not a limit added to a general ComfyUI model.
- FFprobe selects video by absolute stream index, including audio-first files. The timeline reports music alignment only when independent measured beat times are present. It never fits the musical phase to the cuts themselves.
- Spectral analysis uses bounded FFT blocks and FFT autocorrelation. Gray-video analysis uses mapped temporary storage. Event listeners keep the latest state, waveform cache entries are bounded, and thumbnail/ZIP work runs outside the async loop.
- The displayed generation budget counts generated footage and retries, not seconds of GPU time. Fixed per-quality shot-time promises have been removed.
- Motion graphics check decoder/encoder completion and output duration/audio before publishing an export. Crossfade/dissolve approximations are labelled and surfaced as warnings. Take Check remains a technical black/white/noise filter; identity, anatomy and lip-sync still require review.

## Reproduction and installation

The app remains a separate project nested in the custom-node folder in this checkout. Install the node pack and app together, rebuild `frontend/`, and restart ComfyUI and the app. Use `scripts/run_studio.ps1`, optionally `-OutputDir`, `-ComfyUI`, `-ProxyPort` and `-Port`; the launcher changes into the correct project directory.

`requirements-tested.txt` records the exact installed Windows/Python 3.14 environment, including test tools. Use `pip install -r requirements-tested.txt` to reproduce it on that runtime. `requirements.txt` retains the supported direct dependency ranges for other environments. Other Python versions and operating systems are not certified by that snapshot.

Tests cover backend behavior, real FFmpeg media, project independence, dialogue assignment, atomic manifests, workflow structure and the music metric. The generic pytest suite does not run H3. Runtime GPU checks, when performed, are recorded separately with the tested inputs and limits.

Keep the existing model licence notices. These code fixes do not change model licences, constitute permission to publish third-party media or automatically deploy a cloud service.
