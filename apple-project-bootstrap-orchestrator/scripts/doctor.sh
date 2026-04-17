#!/usr/bin/env bash
set -euo pipefail

PROJECT_MODE="new"
required_missing=0

usage() {
  cat <<USAGE
Usage: doctor.sh [--project-mode new|adopt]
USAGE
}

require_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    echo "ok: $name"
  else
    echo "missing: $name"
    required_missing=1
  fi
}

optional_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    echo "optional: $name (found)"
  else
    echo "optional: $name (missing)"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-mode)
      PROJECT_MODE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$PROJECT_MODE" != "new" && "$PROJECT_MODE" != "adopt" ]]; then
  echo "Invalid --project-mode: $PROJECT_MODE" >&2
  exit 1
fi

echo "Apple Project Bootstrap doctor"
echo "project mode: $PROJECT_MODE"

if command -v xcode-select >/dev/null 2>&1; then
  echo "xcode-select: $(xcode-select -p)"
else
  echo "missing: xcode-select"
  required_missing=1
fi

if command -v xcodebuild >/dev/null 2>&1; then
  xcodebuild -version
else
  echo "missing: xcodebuild"
  required_missing=1
fi

require_cmd xcrun
require_cmd python3
require_cmd git
require_cmd jq

if [[ "$PROJECT_MODE" == "new" ]]; then
  require_cmd xcodegen
else
  optional_cmd xcodegen
fi

optional_cmd xcbeautify

if [[ $required_missing -ne 0 ]]; then
  echo ""
  echo "Doctor check failed. Install the missing required tools before continuing." >&2
  exit 1
fi

echo ""
echo "Doctor check passed."
