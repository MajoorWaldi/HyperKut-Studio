# Release checklist

Use this checklist for a reproducible public beta release. A checked implementation in the roadmap is not evidence that every deployment or media asset has been qualified.

- [ ] Publish matching Studio and VideoTools source revisions, including API workflows, manifests and license notices.
- [ ] Verify installation from the published source in a clean environment; record the exact model revisions and GPU configuration.
- [x] Verify the five private remote model files against their source SHA-256 hashes and confirm ComfyUI exposes them; 20 focused remote-transport tests pass.
- [x] Restart ComfyUI after the worker package update and confirm `HyperKutWorkspace`, `HyperKutSnapshotImport`, `HyperKutSnapshotExport` and `HyperKutWorkspaceRelease` load.
- [x] Complete a successful real GPU Music job; the six-second `music-clicks` case passed its render, duration, frame-rate, export-archive and review checks on 2026-10-29.
- [ ] Complete successful real GPU jobs for Text and Remix. Latest run: Remix generated its take but failed during editing with `YuE2 needs a musical direction` (`MajoorYuE2Style`, node `73:9004`). Text failed score preparation because voices had different measure counts in ABC group 131 (`MajoorYuE2Score`, node `73:9012`). No final renders were confirmed for these two modes.
- [x] Confirm the Remix/Music model-patch choice is available in the worker's `ModelPatchLoader` schema; `minimax_h3_fun_controlnet_union_pruned_int8_convrot.safetensors` is now listed alongside the LTX duration head.
- [ ] Record and qualify real-job runtime and peak VRAM use. The latest three-case run took 54m18s overall; the GPU reported 31.84 GiB total VRAM and 0.53 GiB free while the seven-take Music job was active. This is an observation, not a performance qualification.
- [ ] Package only authorized example inputs; validate portable preset assets and missing-input behavior.
- [ ] Verify applicable model/territory permissions and dependency licenses.
- [ ] Verify rights for demo footage, source references, soundtracks, likenesses and voice samples. Attribution alone does not grant permission.
- [ ] Check final media links, documentation links and the actual encoded demonstration.
- [ ] Explain auxiliary tools used to create the presentation and distinguish simulated UI sequences from live generation.
- [ ] Preserve a release identifier and verification record.

For contest submissions, follow the current [official requirements](https://comfy.org/open-source-higgsfield), including demo length, public source, social post and form. Registration, publication and acceptance are separate actions.

## Static-audit corrections (2026-10-29)

HK-A01 through HK-A14 have local implementation fixes and fixture coverage.
This does not qualify the existing remote deployment or change the real-GPU
Text/Remix checkboxes above. Existing services were not restarted or replaced.

- Publication has durable result receipts and recognizes an exact replay,
  including interruption between manifest installation and receipt persistence.
  A genuine conflict blocks only the affected project, not new independent jobs.
- Cancellation waits for a publishing thread to stop before releasing the job.
  Completed analysis restores the project, shots and takes; completed final and
  manual exports can be downloaded and finalized without regenerating video.
  Interrupted generation is not automatically resumed.
- Manual remote exports carry the project identity and the manifest fingerprint
  checked by the editor; a changed project is refused before submission.
- File-backed references sample frames before allocating the output batch, with
  a bounded allocation estimate. Manifest domains and motion contracts are
  validated before publication/generation; hashing no longer needs Python 3.11.
- Launchers verify non-secret configuration identity and bounded transfer limits.
  Readiness is selected-mode/output-closure scoped. Optional finishing fallback
  is shared by the engine entry points and checked in shared-local and remote
  Studio profiles. Manual exports clear obsolete optional-finishing warnings.
- Remote AI edit candidates are explicitly unavailable, even when the
  experimental flag is enabled; no unsupported candidate is created.

### Storage accounting and explicit cleanup

`GET /api/storage` distinguishes local mirror bytes, content-cache inventory,
and pending worker cleanup. Worker disk usage is unknown, not zero.
`POST /api/storage/cache/gc` previews collection; explicitly pass
`?dry_run=false` to delete unreferenced blobs. Collection is refused while jobs,
pending results or other mutations could still use the cache.

Historical result descriptors, pending inputs and retained conflicts protect
their artifacts. Explicit project deletion removes that project's result-history
references; retained conflicts remain protected. Legacy caches without complete
reference provenance remain unclassified and cannot be automatically deleted.
The existing free-takes response's `freed` counts only actual local mirror
deletions; it also exposes separate mirror/cache/worker fields.

Acknowledged worker release cleans its exported snapshot files and unshared
uploaded snapshot. Failed releases have durable cleanup records and can be
retried with `POST /api/storage/worker/cleanup`. Deploy the matching experimental
worker revision before relying on acknowledged cleanup. See
[artifact retention](artifact-retention.md).

Qualification still required: a fresh install at the announced minimum Python,
real high-resolution memory measurements, and remote Draft execution after
deploying matching Studio/VideoTools/worker sources. Snapshot transfer remains
whole-bundle; incremental transport is not implemented by these corrections.

Local validation after corrections:

- Studio fixtures: **413 passed, 7 skipped** (real GPU cases require `--real`).
- Engine integration: **498 passed, 1 skipped**, using the existing ComfyUI
  Python environment.
- Frontend: **33 tests passed**, TypeScript build and focused lint passed.
- Both launcher scripts passed PowerShell parsing; both repositories passed
  `git diff --check`.
- Pylance found all six resolved `_run` call sites signature-compatible.

The existing experimental Git-ignore policy was preserved. Several remote
transport modules remain ignored; the publication/clean-clone checklist must
include the complete matching implementation, not just tracked-file diffs.
No commit, push, service restart or real GPU generation was performed.

## Selected-mode dependency readiness

`GET /api/health?mode=remix|text|music` reports the selected mode (default:
`remix`), not the union of all exported workflows. Optional media presence can be
specified with `refs=0..5`, `ref_video=true|false`, and `voice=true|false`.
Readiness fills the three execution-phase templates, removes absent media, and
checks only the upstream closure of output sinks. Unused local-edit templates,
disconnected loaders, and other modes cannot block this result. Optional graphic
finishing and masking are excluded from this conservative baseline; runtime
availability/fallback handling still applies.

The Studio refreshes this status when the mode or optional media presence changes
and ignores superseded responses. Missing classes and exact selected model names
are shown for that selection. Both legacy combo lists and V3 `COMBO` options are
supported, including empty model lists and the `ModelPatchLoader.name` input.
This status is advisory: before submission, execution must check its actual graph
after optional removal/fallback, using the same output closure and model-enum
helpers. It is not proof of GPU execution or model quality.

[Installation](installation.md) · [Validation](validation-summary.md) · [Licenses](../LICENSES.md)
