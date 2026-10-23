# Experimental native GCC bootstrap

This branch preserves the incomplete native GCC 5.4 bootstrap investigation
separately from the verified userspace feed integration. It is not ready to
merge or publish. The ARM GCC 4.8 bootstrap lacks private runtime macros and
does not accept the GCC 5 runtime build's `-std=gnu++14` option.

The patch addresses floating-point modes, gcov vtables and target CRT sections.
Local ARM source checks passed for complex arithmetic, indirect-call profiling
and CRT begin/end/PIC variants under a target-header fixture. The complete
configured build still fails at C++14; do not bypass compiler guards or claim
that the resulting runtime is usable. A suitable bootstrap compiler remains
necessary before publishing the native compiler.
