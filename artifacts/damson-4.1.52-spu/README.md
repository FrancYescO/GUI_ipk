# Router-tested SPU, Damson Linux 4.1.52

Published by the main branch in:
https://francyesco.github.io/GUI_ipk/kernel/4.1.52/

The SPU source and patches were merged into `kmods-4.1.52`; the current main
feed assembler imports this separately verified artifact directory, preserving
the existing networking and userspace feeds.

Original successful Actions build:
https://github.com/FrancYescO/GUI_ipk/actions/runs/39433551005

The integrated main-compatible build was also verified by:
https://github.com/FrancYescO/GUI_ipk/actions/runs/39448024517
Its `bcmspu.ko` is byte-identical (SHA256
`0b743d61ae454e20d2a9a9a3099c9be5f85c7e495773aad4d1d137ab9ac42cd7`).
IPK timestamps may differ; this directory keeps the original package actually
extracted and tested on the router.

See `build/vbntj-spu-test/VALIDATION.md` for the functional tests and limitations.
No boot autoload is included. SHA256-128 uses software fallback. BLOG ESP flow
offload is disabled by default; Windows/DHCP interoperability is not proven.
Hardware Runner packet drops remain observable under TCP/UDP load.
