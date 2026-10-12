# Historical source overlay

The archived OpenWrt buildroot was created without the contents of directories
named `bin`. That also removed source payloads used by `base-files`,
`qos-scripts`, and the `missing-macros` host tool.

This directory restores the missing OpenWrt 18.06 files before compilation.
Other missing `bin` payloads in the package and LuCI feeds are restored from
the Git object databases and pinned commits already embedded in the archive.
The overlay is source-only; it is never copied directly into the published
OPKG feed.
