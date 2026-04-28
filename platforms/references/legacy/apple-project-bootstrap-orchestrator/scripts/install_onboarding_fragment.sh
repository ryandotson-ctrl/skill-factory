#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: install_onboarding_fragment.sh --project-dir PATH [--profile generic|pfe] [--mode install|upgrade] [--dry-run]
USAGE
}

PROJECT_DIR=""
PROFILE_MODE="generic"
MODE="install"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --profile)
      PROFILE_MODE="$2"
      shift 2
      ;;
    --mode)
      MODE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
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

if [[ -z "$PROJECT_DIR" ]]; then
  echo "Missing --project-dir" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSET_ROOT="$SCRIPT_DIR/../assets/onboarding"
SOURCE_FILE="$ASSET_ROOT/generic-AGENTS.md"
if [[ "$PROFILE_MODE" == "pfe" ]]; then
  SOURCE_FILE="$ASSET_ROOT/pfe-AGENTS.md"
fi

AGENTS_TARGET="$PROJECT_DIR/AGENTS.md"
FRAGMENT_TARGET="$PROJECT_DIR/AGENTS.apple-project-bootstrap.md"

if [[ -f "$FRAGMENT_TARGET" && "$MODE" == "install" ]]; then
  echo "Refusing to overwrite existing $FRAGMENT_TARGET in install mode." >&2
  exit 1
fi

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[dry-run] Would install onboarding guidance from $SOURCE_FILE"
  if [[ -f "$AGENTS_TARGET" ]]; then
    echo "[dry-run]   target: $FRAGMENT_TARGET"
  else
    echo "[dry-run]   target: $AGENTS_TARGET"
  fi
  exit 0
fi

if [[ -f "$AGENTS_TARGET" ]]; then
  cp "$SOURCE_FILE" "$FRAGMENT_TARGET"
else
  cp "$SOURCE_FILE" "$AGENTS_TARGET"
fi

echo "Installed onboarding guidance to $PROJECT_DIR"
