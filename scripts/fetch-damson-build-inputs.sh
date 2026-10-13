#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
input_dir="${1:-$repo_root/.cache/sources/damson}"
mode="${DAMSON_INPUTS_MODE:-release}"
release_tag="${DAMSON_INPUTS_TAG:-damson-build-inputs-v1}"
repository="${DAMSON_INPUTS_REPOSITORY:-${GITHUB_REPOSITORY:-FrancYescO/GUI_ipk}}"
gpl_commit=af23960e39003ba7788f5ced0c256b1bc676a712
gpl_archive="vmg8825_b50b-$gpl_commit.tar.gz"

case "$mode" in
  release|bootstrap|verify) ;;
  *) echo "Unsupported DAMSON_INPUTS_MODE: $mode" >&2; exit 1 ;;
esac
mkdir -p "$input_dir"

verify_file() {
  local actual
  actual="$(sha256sum "$1")"
  [[ "${actual%% *}" == "$2" ]]
}

while IFS=$'\t' read -r filename checksum origin _provenance; do
  [[ -z "$filename" || "$filename" == \#* ]] && continue
  if [[ "${DAMSON_INCLUDE_GPL:-1}" == 0 && "$filename" == "$gpl_archive" ]]; then
    continue
  fi
  destination="$input_dir/$filename"
  if [[ -f "$destination" ]]; then
    verify_file "$destination" "$checksum" || {
      echo "Invalid cached Damson input: $destination" >&2
      exit 1
    }
    continue
  fi
  if [[ "$mode" == verify ]]; then
    echo "Missing Damson input: $destination" >&2
    exit 1
  fi
  partial="$(mktemp "$input_dir/.$filename.XXXXXX")"
  temporary_checkout=""
  trap 'rm -f "$partial"; if [[ -n "$temporary_checkout" ]]; then rm -rf "$temporary_checkout"; fi' EXIT
  if [[ "$mode" == release ]]; then
    # Normal builds never fall back to upstream mirrors. Missing releases or
    # assets are errors, so dependency loss is detected instead of hidden.
    if command -v gh >/dev/null 2>&1; then
      rm -f "$partial"
      download_dir="$(mktemp -d "$input_dir/.download.XXXXXX")"
      temporary_checkout="$download_dir"
      gh release download "$release_tag" --repo "$repository" \
        --pattern "$filename" --dir "$download_dir"
      mv "$download_dir/$filename" "$partial"
      rm -rf "$download_dir"
      temporary_checkout=""
    else
      wget --tries=3 --timeout=30 --output-document="$partial" \
        "https://github.com/$repository/releases/download/$release_tag/$filename"
    fi
  elif [[ "$filename" == "$gpl_archive" ]]; then
    temporary_checkout="$(mktemp -d "$input_dir/.gpl.XXXXXX")"
    git init --quiet "$temporary_checkout"
    git -C "$temporary_checkout" remote add origin https://github.com/avwarez/vmg8825_b50b.git
    git -C "$temporary_checkout" fetch --depth 1 origin "$gpl_commit"
    test "$(git -C "$temporary_checkout" rev-parse FETCH_HEAD)" = "$gpl_commit"
    git -C "$temporary_checkout" archive --format=tar "$gpl_commit" | gzip -n -6 > "$partial"
    rm -rf "$temporary_checkout"
    temporary_checkout=""
  else
    wget --tries=3 --timeout=30 --output-document="$partial" "$origin"
  fi
  verify_file "$partial" "$checksum" || {
    echo "Invalid downloaded Damson input: $filename" >&2
    exit 1
  }
  mv "$partial" "$destination"
  trap - EXIT
done < "$repo_root/build/vbntj/inputs.tsv"

echo "Verified Damson inputs in $input_dir ($mode)"
