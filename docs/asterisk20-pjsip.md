# Experimental Asterisk 20 SIP/PJSIP profile

This profile builds Asterisk 20.21.0 with PJPROJECT 2.14.1 for the existing
ARM Cortex-A9, GCC 4.8 and glibc toolchain. It selects PJSIP, RTP, basic bridging,
G.711/G.722 codecs and WAV/PCM formats. Dial, playback, echo and the configuration
dialplan are embedded in the base Asterisk recipe.

Jansson is updated from 2.10 to 2.14 in this profile because Asterisk 20 requires
at least 2.11. The source metadata comes from `openwrt/openwrt` commit
`33063b4ccf00d39393796499b23df55187b192dc`. The legacy autotools recipe is retained,
with autoreconf enabled for the GitHub source archive.

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
| Jansson 2.14 | `c739578bf6b764aa0752db9a2fdadcfe921c78f1228c7ec0bb47fa804c55d17b` |

The Asterisk hash matches the upstream release checksum; the PJPROJECT hash
matches the pinned OpenWrt recipe. OpenWrt also checks these hashes when building.

In the package workflow select `build_profile=asterisk20`, with an optional
`package_targets=feeds/telephony/asterisk`. The profile imports the new recipes
into a disposable buildroot and replaces its PJPROJECT recipe. The ordinary
userspace profile retains its current recipes and PJPROJECT ABI. Targeted
output is uploaded as an artifact; this profile does not deploy to Pages.

The first run, [38298772454](https://github.com/FrancYescO/GUI_ipk/actions/runs/38298772454),
produced all nine PJPROJECT library IPKs. Asterisk stopped during configuration
because the original Jansson 2.10 was too old. Run
[38449790492](https://github.com/FrancYescO/GUI_ipk/actions/runs/38449790492)
produced the Jansson 2.14 IPK and passed Asterisk configuration, then stopped at
a C99 loop declaration in `main/stasis_channels.c`. The recipe now selects GNU99
for C sources and removes that flag from the inherited C++ flags. Run
[38453060032](https://github.com/FrancYescO/GUI_ipk/actions/runs/38453060032) succeeded,
producing 15 Asterisk IPKs, nine PJPROJECT library IPKs and Jansson 2.14.
Control metadata confirms the expected versions and ARM architecture; all declared
dependencies of those packages are present in the artifact. The core executable,
PJSIP channel and RTP modules are present. The 87 ELF files in the Asterisk/PJPROJECT
packages are ELF32 ARM without the hard-float ABI flag.

Router runtime verification remains pending. The restored firmware
toolchain and current OpenSSL library remain the starting compatibility base;
SIP registration, calls, audio and TLS have not yet been verified on the router.
