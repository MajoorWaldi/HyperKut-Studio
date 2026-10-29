# Snapshot artifact retention

## Local content-addressed cache

`LocalArtifactStore.inventory(retained_snapshots=(), *, retained_refs=(),
references_complete=False)` reports digest blobs, their physical sizes and their
`retained`, `reclaimable` or `unclassified` state. Pass `ProjectSnapshot` objects
for **all retained revisions**, not only the latest project manifest. Their
manifest and asset references are retained automatically. Pass additional
`ArtifactRef` objects through `retained_refs` for pending/active operations.

Coverage is unknown by default: a blob absent from the supplied references is
**unclassified, not garbage**. Missing, unreadable or incomplete reference
metadata must not be interpreted as an empty authoritative reference set.

`collect_garbage()` accepts the same arguments and defaults to `dry_run=True`.
Deletion requires both `references_complete=True` and `dry_run=False`. The
caller must hold its project/operation metadata lock while gathering references
and throughout collection, so no new historical or active reference can appear
between enumeration and deletion. The cache's file lock serializes cooperating
cache readers, writers and collectors; it cannot protect external metadata.

The report contains pre-collection inventory totals, `removed_count`,
`removed_bytes`, and per-file `errors`. Removed bytes count only successful
unlinks, not candidate sizes, mirrored project files or remote worker files.
Re-inventory for post-collection totals. Unknown/non-digest files and incoming
transfer scratch files are not included or removed by GC. Interrupted-transfer
cleanup remains a separate `discard_incomplete()` operation.

Purging a project mirror is not proof that its cached blobs are unreferenced:
historical snapshots and pending remote operations may still need them. Until
the application can establish complete reference coverage it must report cache
bytes separately and leave them intact.

## Manifest validation boundary

Snapshot capture, verification and materialization reuse the VideoTools
manifest schema. The manifest is rejected before worker files are materialized
if its domain values are invalid, including non-integer frame/rate fields,
zero frame-rate denominators, invalid dimensions, non-finite or non-positive
durations, and inconsistent shot/revision lineage.

## Worker acknowledgement

New worker operations persist ownership receipts in the worker output's
`_hyperkut_retention` directory. They own the exact published ZIP/descriptor and,
for imports/transforms, the exact uploaded input bytes. Receipts survive worker
restart and are not project snapshots or user exports.

`HyperKutWorkspaceRelease(operation_id, acknowledged=False)` keeps its original
workspace-only meaning. Published files, uploaded snapshots and their receipt
remain available for a later acknowledgement. New operations cannot be
released while active: they become completed only after snapshot publication.

After the receiver has verified, applied **and durably recorded** the result,
submit `HyperKutWorkspaceRelease` with `acknowledged=True`. This removes the
workspace, owned published ZIP/descriptor and upload, then the receipt.
A repeated acknowledged release is harmless. `removed_bytes`/`removed_files` in
the node's JSON text count only removed published/uploaded files, not scratch
workspace contents; they are worker metrics, not local cache/mirror metrics.

Deletion validates stored file identities before removing anything. Replaced
uploads are never silently removed. An upload shared by another active or
completed-but-unacknowledged receipt is retained until the last owner
acknowledges. Unknown legacy published files without receipts are left intact;
no directory-wide sweep, timestamp heuristic or automatic eviction is used.
The retention lock prevents cleanup racing import/export/transform execution.
Active/failed generation receipts are retained conservatively rather than
assuming that a disconnected client means execution has stopped.

Standalone `HyperKutSnapshotTransform` accepts an optional `operation_id`.
If omitted it generates one and returns it in UI `text`; retain that ID for the
acknowledgement. Existing transform inputs and snapshot JSON output remain
unchanged.

Fixtures: `tests/test_artifact_store.py` and `tests/test_worker_retention.py`.
These exercise filesystem contracts without a live Comfy server or GPU.
