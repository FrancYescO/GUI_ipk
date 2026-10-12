# Userspace source updates

The initial batch imports source metadata from the official OpenWrt packages
feed at commit `eb758024a9c2fb841326ccd8e59d98bd3b975ff9`
(`openwrt-23.05`). The existing build framework, installation paths and runtime
dependencies are retained. Upstream archive SHA256 hashes are checked before
the recipes are committed and again by the OpenWrt downloader during builds.

| Recipe | Previous version | Candidate version |
| --- | --- | --- |
| pv | 1.5.3 | 1.6.6 |
| tree | 1.8.0 | 2.1.1 |
| htop | 2.2.0 | 3.3.0 |

Htop's optional sensors, capabilities, delay accounting and unwinding integrations
are disabled to retain the existing dependency set. Unicode and hwloc remain
disabled as in the original recipe.

The updates are applied by `patches/userspace-package-updates.patch` for userspace
builds. Test the three recipes with the `package_targets` workflow input:

```text
feeds/packages/pv feeds/packages/tree feeds/packages/htop
```

A successful cross-build confirms compilation and package generation. Runtime
operation on the router still needs verification before claiming firmware
compatibility. This batch is a compatibility step, not a claim that these are
the newest available upstream releases.
