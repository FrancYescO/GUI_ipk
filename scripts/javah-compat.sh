#!/usr/bin/env bash
set -euo pipefail

# RXTX still invokes javah, which was removed after JDK 8. Recompile its
# Java sources with javac -h to generate the same JNI headers.
classpath=
output_dir=
classes=()
while (($#)); do
  case "$1" in
    -classpath|-cp)
      classpath="$2"
      shift 2
      ;;
    -d)
      output_dir="$2"
      shift 2
      ;;
    -jni)
      shift
      ;;
    -*)
      echo "Unsupported javah option: $1" >&2
      exit 2
      ;;
    *)
      classes+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$classpath" || -z "$output_dir" || ${#classes[@]} -eq 0 ]]; then
  echo 'Expected javah -classpath PATH -d DIR -jni CLASS...' >&2
  exit 2
fi

sources=()
for class in "${classes[@]}"; do
  source_file="src/${class//.//}.java"
  if [[ ! -f "$source_file" ]]; then
    echo "Missing JNI source: $source_file" >&2
    exit 1
  fi
  sources+=("$source_file")
done

mkdir -p "$output_dir"
javac -classpath "$classpath" -d . -h "$output_dir" -source 6 -target 6 "${sources[@]}"
