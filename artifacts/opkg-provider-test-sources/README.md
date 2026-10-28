# Pinned source-only test inputs

These archives build the unmodified package manager used by the ARM firmware.
They are not installable packages and are not added to any public OPKG feed.

- opkg: https://github.com/openwrt/opkg-lede/archive/4bd8601ebd95c130e504cc724b0c5eb163050982.tar.gz
  SHA256 `38e8996e1776b3ce10897ee4fb6afc60910b399ddd53e718e72f3308633bca3f`
- libubox: https://github.com/openwrt/libubox/archive/fd57eea9f37e447814afbf934db626288aac23c4.tar.gz
  SHA256 `cc059c5d48dd24182a917c758ca2e6710db17d3a5c2cc7474f1cb40ce5b40c72`

Copyright and license notices are included in the archives (opkg GPL-2.0;
libubox files carry their individual ISC/BSD/LGPL notices). No compatibility
patch is applied: tests must pass with the old Replaces-parser defect present.
