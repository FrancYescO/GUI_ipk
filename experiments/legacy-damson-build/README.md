# Historical Damson build snapshot

Source commit: `d56c2832c0bb0c88c78f173a8b15311616bbfb68` (`kmods-4.1.52`). The complete original
history is a merge parent of the consolidation on main.

These older entry points, input manifests, patches and raw/module IPKs are
retained for provenance. Their paths refer to the original repository layout;
this directory is not an active buildroot and is not used by publication.
The nested `.github/workflows` directory is historical data, not a workflow
installed at the repository root. Existing kernel artifacts, ABI registries,
provider fixes and stable build entry points on main remain authoritative.

To reproduce a historical build, check out the full source commit in an
isolated worktree and follow that revision's instructions. Do not copy old
IPKs into a current feed: they predate the current ABI/provider normalization.
The Runner SHA256 experiment has documented stalls/restarts and remains
quarantined in `../spu-sha256`; no modules are loaded by this integration.
