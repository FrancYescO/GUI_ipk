#!/usr/bin/env bash
set -euo pipefail

artifact_dir="${1:-dist/vbntj-kmods}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kernel_package="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["kernel_package"])' "$repo_root/build/kernel-profiles/vbntk-4.1.52.json")"

if [[ ! -d "$artifact_dir" ]]; then
  echo "Artifact directory does not exist: $artifact_dir" >&2
  exit 1
fi

if find "$artifact_dir" -maxdepth 1 -type f \
  \( -name Packages -o -name Packages.gz -o -name Packages.manifest -o -name Packages.sig \) \
  -print -quit | grep -q .; then
  echo "Manual kernel artifacts must never contain an OPKG feed index" >&2
  exit 1
fi

ipk_count=0
while IFS= read -r -d '' ipk; do
  ipk_count=$((ipk_count + 1))
  filename="$(basename "$ipk")"
  package_arch=brcm963xx
  if [[ "$filename" =~ ^kmod-(bcmspu|cdc-ether|rndis-host)-4\.1\.52-manual_4\.1\.52-[0-9]+_arm_cortex-a9\.ipk$ ]]; then
    package_arch=arm_cortex-a9
  elif [[ ! "$filename" =~ ^kmod-[a-z0-9.-]+-4\.1\.52-manual_4\.1\.52-[0-9]+_brcm963xx\.ipk$ ]]; then
    echo "Unexpected manual IPK filename: $filename" >&2
    exit 1
  fi

  outer_members="$(tar -tzf "$ipk" | LC_ALL=C sort)"
  expected_outer=$'./control.tar.gz\n./data.tar.gz\n./debian-binary'
  if [[ "$outer_members" != "$expected_outer" ]]; then
    echo "Unexpected outer payload in $filename" >&2
    printf '%s\n' "$outer_members" >&2
    exit 1
  fi

  control_members="$(tar -xOzf "$ipk" ./control.tar.gz | tar -tzf - | LC_ALL=C sort)"
  if [[ "$control_members" != './control' ]]; then
    echo "Maintainer scripts or unexpected control files in $filename" >&2
    printf '%s\n' "$control_members" >&2
    exit 1
  fi

  control="$(tar -xOzf "$ipk" ./control.tar.gz | tar -xOzf - ./control)"
  package_name="${filename%%_*}"
  package_version="${filename#*_}"
  package_version="${package_version%%_*}"
  legacy_package_name="${package_name/-4.1.52-manual/-damson-4.1.52-manual}"
  for required in \
    "Package: $package_name" \
    "Version: $package_version" \
    "Conflicts: $legacy_package_name" \
    "Replaces: $legacy_package_name" \
    "Architecture: $package_arch" \
    'X-Kernel-Target: VBNT-K' \
    'X-Kernel-Profile: 4.1.52-vbntk' \
    'X-Firmware: 19.4.1051-3401200' \
    "Depends: kernel (= $kernel_package)" \
    'X-Kernel-Vermagic: 4.1.52 SMP preempt mod_unload ARMv7' \
    'X-Manual-Install-Only: yes'; do
    if ! grep -Fxq "$required" <<< "$control"; then
      echo "Missing control guard '$required' in $filename" >&2
      exit 1
    fi
  done

  data_members="$(tar -xOzf "$ipk" ./data.tar.gz | tar -tzf -)"
  if [[ "$(wc -l <<< "$data_members" | tr -d ' ')" -ne 1 ]] ||
     [[ ! "$data_members" =~ ^\./lib/modules/4\.1\.52/[a-zA-Z0-9_.-]+\.ko$ ]]; then
    echo "IPK must contain exactly one VBNT-K 4.1.52 module: $filename" >&2
    printf '%s\n' "$data_members" >&2
    exit 1
  fi

  module_name="$(basename "$data_members")"
  if [[ ! -f "$artifact_dir/$module_name" ]]; then
    echo "Sibling raw module missing for $filename: $module_name" >&2
    exit 1
  fi
  packaged_sha256="$(tar -xOzf "$ipk" ./data.tar.gz | tar -xOzf - "$data_members" | sha256sum | awk '{print $1}')"
  raw_sha256="$(sha256sum "$artifact_dir/$module_name" | awk '{print $1}')"
  if [[ "$packaged_sha256" != "$raw_sha256" ]]; then
    echo "Packaged module differs from raw artifact: $filename" >&2
    exit 1
  fi
done < <(find "$artifact_dir" -maxdepth 1 -type f -name '*.ipk' -print0)

if [[ "$ipk_count" -eq 0 ]]; then
  echo "No manual VBNT-K IPKs found in $artifact_dir" >&2
  exit 1
fi

echo "Verified $ipk_count manual-only VBNT-K 4.1.52 IPK artifact(s)"
