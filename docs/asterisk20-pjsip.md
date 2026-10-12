# Experimental Asterisk 20 SIP/PJSIP profile

This profile builds Asterisk 20.21.0 with PJPROJECT 2.14.1 for the existing
ARM Cortex-A9, GCC 4.8 and glibc toolchain. It selects PJSIP, RTP, basic bridging,
G.711/G.722 codecs and WAV/PCM formats. Dial, playback, echo and the configuration
dialplan are embedded in the base Asterisk recipe.

Recipes, service files and build patches come from `openwrt/telephony` commit
`98c8a5aa4624312ed758e2e2b6d4039050a1649d` (OpenWrt 23.05). The Asterisk recipe
has been advanced from 20.8.1 to 20.21.0. Patch `180-app_queue_time_t.patch` is
omitted because its target code has changed in the newer source; this profile
does not select the queue module. The remaining patches apply sequentially to
the downloaded Asterisk and PJPROJECT sources.

Verified source hashes:

| Source | SHA256 |
| --- | --- |
| Asterisk 20.21.0 | `13fd6e8f1fbb19a3174af82a388dd72c87eb2c92d32fca83c4d51bfab03f686a` |
| PJPROJECT 2.14.1 | `6140f7a97e318caa89c17e8d5468599671c6eed12d64a7c160dac879ba004c68` |

The Asterisk hash matches the upstream release checksum; the PJPROJECT hash
matches the pinned OpenWrt recipe. OpenWrt also checks these hashes when building.

In the package workflow select `build_profile=asterisk20`, with an optional
`package_targets=feeds/telephony/asterisk`. The profile imports the new recipes
into a disposable buildroot and replaces its PJPROJECT recipe. The ordinary
userspace profile retains its current recipes and PJPROJECT ABI. Targeted
output is uploaded as an artifact; this profile does not deploy to Pages.

Build and router runtime verification are pending. The restored firmware
toolchain and current OpenSSL library remain the starting compatibility base;
SIP registration, calls, audio and TLS have not yet been verified on the router.
