#!/bin/sh
# Print a proposed source configuration. Never change the router configuration.
set -eu
manifest="${1:?Usage: print-opkg-sources.sh /path/to/feeds.json [--asterisk20]}"
jsonfilter -i "$manifest" -e '@.userspace[*].source'
kernel="$(awk 'BEGIN {RS=""; FS="\n"} {p="";v=""; for(i=1;i<=NF;i++) {if($i=="Package: kernel") p="kernel"; if($i ~ /^Version: /) v=substr($i,10)} if(p=="kernel") print v}' /usr/lib/opkg/status)"
for version in $(jsonfilter -i "$manifest" -e '@.kernel.profiles[*].kernel_package'); do
    if [ -n "$kernel" ] && [ "$kernel" = "$version" ]; then
        printf 'src/gz modgui_kernel %s\n' "$(jsonfilter -i "$manifest" -e '@.kernel.url')"
        break
    fi
done
if [ "${2:-}" = '--asterisk20' ]; then
    printf 'src/gz modgui_asterisk20 %s\n' "$(jsonfilter -i "$manifest" -e '@.optional.asterisk20')"
fi
