# OpenMP runtime

The original ARM GCC 4.8 toolchain does not contain `libgomp.so` or
`libgomp.spec`. Its bundled package declaration therefore cannot supply an
OpenMP runtime. The userspace profile replaces that declaration with a
standalone library recipe; the target compiler stays disabled.

The recipe builds only the GNU GCC 4.8.3 `libgomp` subdirectory, using the
existing cross-compiler. Its source archive is pinned by SHA-256. The runtime
package contains the versioned `libgomp.so.1` library and declares its GCC and
pthread dependencies. Development staging includes `omp.h`, the linker symlink,
and `libgomp.spec`. A cross-build using `-fopenmp` must also pass
`-B$(STAGING_DIR)/usr/lib/` so that the compiler can find the staged specs file.

Use `package_targets=libs/libgomp`, `build_profile=userspace` and
`publish_pages=false` in the manual userspace workflow for a targeted build.
A successful targeted artifact can be included with the existing incremental
repair workflow. Kernel builds do not apply this userspace replacement.

The ARM smoke test in `tests/libgomp-smoke.c` creates four OpenMP threads and
checks a parallel reduction. Emulated execution supplements package and ELF
checks; router runtime testing remains separate.
