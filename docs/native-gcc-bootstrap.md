# Experimental native GCC bootstrap

The incomplete native GCC 5.4 bootstrap investigation is preserved on main
as a disabled experiment. It is not ready to enable in the shared build or
publish. The ARM GCC 4.8 bootstrap lacks private runtime macros and
does not accept the GCC 5 runtime build's `-std=gnu++14` option.

The patch addresses floating-point modes, gcov vtables and target CRT sections.
Local ARM source checks passed for complex arithmetic, indirect-call profiling
and CRT begin/end/PIC variants under a target-header fixture. The complete
configured build still fails at C++14; do not bypass compiler guards or claim
that the resulting runtime is usable. A suitable bootstrap compiler remains
necessary before publishing the native compiler.

The recipe patch is copied only when `ENABLE_NATIVE_GCC_BOOTSTRAP=1`,
`USERSPACE_ONLY=1`, and the explicit target list includes
`feeds/packages/gcc`. Normal builds do not apply it. This opt-in does not
make the compiler build supported or bypass the C++14 requirement.
