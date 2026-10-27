# Withheld Linux 4.1.52 xt_nat candidate

The raw module here uses the corrected Technicolor NAT range layout, but was
not loaded: during preparation of its test, removing the stock `xt_nat` module
caused SSH disconnection followed by a changed boot ID. The candidate had not
yet been loaded. The cause of that stock-removal failure is unresolved.

Do not repeat this stock-module removal on a live router. No installable IPK
is published here or included in the normal OPKG feed. The feed assembler
rejects this package based on the validation record. The raw module is retained
only for offline investigation; it is not runtime validated.
