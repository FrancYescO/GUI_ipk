#!/bin/sh
# Invoke OPKG with PATH pointing to a private directory containing this as wget.
# curl uses its normal verified CA store, or the explicit CURL_CA_BUNDLE.
set -eu
out= url=
while [ "$#" -gt 0 ]; do
    case "$1" in
        -O) out="$2"; shift 2 ;;
        -t|-T|--timeout|--tries) shift 2 ;;
        -q|--quiet) shift ;;
        https://*) url="$1"; shift ;;
        *) echo "Unsupported wget argument: $1" >&2; exit 2 ;;
    esac
done
[ -n "$out" ] && [ -n "$url" ] || exit 2
exec /usr/bin/curl -fLsS --connect-timeout 20 --max-time 300 -o "$out" "$url"
