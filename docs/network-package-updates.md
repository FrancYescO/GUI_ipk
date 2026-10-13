# Network package update candidates

| Recipe | Archived version | Candidate version |
| --- | --- | --- |
| iperf3 | 3.5 | 3.17.1-4 |
| tcpdump / tcpdump-mini | 4.9.3 | 4.99.4-1 |
| ddns-scripts and provider extensions | 2.7.8 | 2.8.2-43 |

Source: OpenWrt packages commit `eb758024a9c2fb841326ccd8e59d98bd3b975ff9`
for iperf3/DDNS and OpenWrt core commit
`33063b4ccf00d39393796499b23df55187b192dc` for tcpdump (OpenWrt 23.05).
The iperf3 and tcpdump source archive SHA256 hashes match the pinned recipes.
DDNS scripts and provider data are vendored directly from the pinned feed.

The complete recipes replace the archived directories only for userspace
builds. Iperf3 also produces libiperf3; libpthread dependencies are explicit.
Tcpdump retains the archived variant directory layout, uses GNU C99 for loop
declarations, keeps linker section cleanup flags, and declares the archived
librpc dependency found in the full-feed build. The iperf3 SSL binary
explicitly depends on libiperf3. DDNS explicitly depends on jshn for JSON
provider definitions.

Test with the workflow's package_targets input:

```text
network/utils/iperf3 network/utils/tcpdump feeds/packages/ddns-scripts
```

Cross-build verification is pending. Throughput and authentication, packet
capture, existing DDNS configurations and the legacy LuCI DDNS interface
require router runtime checks. The newer iperf3 uses its upstream fallback
when this GCC 4.8 toolchain lacks the C11 stdatomic header; multistream counter
accuracy needs runtime verification. No DDNS provider account is contacted
by the build test.
