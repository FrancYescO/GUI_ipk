# Consolidation of the remaining development branches

The consolidation preserves the original branch heads in merge ancestry so
that the work and its history remain available after branch cleanup.

| Work | Result on main |
| --- | --- |
| PR #44 / LuCI | Pinned final 18.06 source delta, scanner settings, source-mirror repair and verified cross-build provenance |
| PR #42 / SPU CBC | Private, explicitly selected laboratory profile; no stable module replacement or automatic device loading |
| Userspace fixes | Compiler-based detection of the actual switch UAPI; predecessor patches retained without stacking them |
| Native GCC | Incomplete bootstrap patch retained behind an explicit target and environment opt-in; disabled by default |
| Kernel development branch | Current pipeline and ABI/provider metadata retained; historical entry points and IPKs under `experiments/legacy-damson-build` |
| Runner SHA256 | Source, diagnostics and negative results retained in `experiments/spu-sha256`; historical profiles remain inactive |

The legacy archive is outside the stable artifact registry and the workflow
root. Its files are reference material, not release inputs. In particular, the
older IPKs are not copied into current feeds. The current SPU CBC profile uses
private device and algorithm names and produces a separate raw bundle.

The old partial GCC patch is not applied alongside its fuller successor. The
native GCC bootstrap still requires a compiler supporting the C++14 runtime
build; integrating the investigation does not claim that it builds or is safe
to publish. `ENABLE_NATIVE_GCC_BOOTSTRAP=1` additionally requires an explicit
`feeds/packages/gcc` target and `USERSPACE_ONLY=1`.

The switch UAPI probe uses the selected C compiler and actual kernel headers.
It checks every link identifier used by the guarded code; names mentioned only
in comments and incomplete vendor APIs do not enable the link path.

## Source heads

- `main`: `bee39fdf2df8a8114ecf52cd6c9da832754257d7`
- `codex/luci-18.06-maintenance`: `509c1ae7ec83a3902056165f4199a32159d50d48`
- `codex/spu-cbc-prototype`: `d0983a7db9ec83c4c0c6a7086a36d282a21b8456`
- `codex/native-gcc-bootstrap`: `84777b0740c197791a91b856fe8cc48188cc3802`
- `codex/userspace-link-python-fixes`: `77e528b7c74dcec0ee89f2cb1d635d29dcd56a16`
- `kmods-4.1.52`: `d56c2832c0bb0c88c78f173a8b15311616bbfb68`

## Verification

The combined local suite passed: 148 tests, three platform-specific skips on
macOS. Six added regression cases cover the experimental GCC preflight and
complete, incomplete and comment-only switch headers. Shell syntax and patch
application checks passed. The targeted LuCI build and ARM payload checks are
recorded in `docs/luci-update.md`; SPU CBC hardware evidence remains in its
validation directory. Linux source checks and a combined LuCI/swconfig build
are run on the consolidation branch before merging.

Normal main-branch publication automation remains enabled with the user's
approval. Its existing complete-feed, payload and provenance checks apply;
this consolidation does not promote the archived kernel packages or the
unfinished GCC/Runner experiments.
