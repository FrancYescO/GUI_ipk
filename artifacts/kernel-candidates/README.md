# Preserved kernel candidate inputs

`vbnto.tar.gz` and `vbnts.tar.gz` preserve the original 220 and 212 staged
IPKs, module manifests, runtime configurations and build diagnostics. They
replace the two redundant candidate Releases as publisher inputs.

The bundle hashes and source commits are pinned in
`build/kernel-candidates/sources.json`. Each original IPK retains its pinned
checksum. Publishing runs offline from these bundles and verifies package
metadata, kernel dependency, module SHA-256 and staging-only paths.
The quarantined xt_nat payload is not included in the bundles or feeds.

Future compilations upload workflow artifacts. Promotion to the public feed
requires updating the pinned bundle and its manifests; the build workflows
do not recreate candidate Releases.
