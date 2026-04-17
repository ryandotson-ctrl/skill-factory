#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: init.sh [options]

Options:
  --project-mode new|adopt
  --name "AppName"
  --bundle-id "com.example.AppName"
  --platform ios|ipados|macos|visionos|watchos
  --ui swiftui|uikit|appkit
  --output /path/to/output
  --generator-command "xcodegen generate"
  --profile generic|pfe
  --agent-name NAME
  --deployment-target VERSION
  --sim-name NAME
  --git-init auto|never
  --git-commit prompt|always|never
  --with-build-harness | --skip-build-harness
  --with-task-templates | --skip-task-templates
  --with-onboarding | --skip-onboarding
  --with-release-profile | --skip-release-profile
  --dry-run
  --no-prompt
USAGE
}

PROJECT_MODE="new"
APP_NAME=""
BUNDLE_ID=""
PLATFORM=""
UI="swiftui"
OUTPUT=""
GENERATOR_COMMAND="xcodegen generate"
PROFILE_MODE="generic"
AGENT_NAME_INPUT="${AGENT_NAME:-}"
DEPLOYMENT_TARGET=""
SIM_NAME=""
INSTALL_BUILD_HARNESS=1
INSTALL_TASK_TEMPLATES=0
INSTALL_ONBOARDING=0
WRITE_RELEASE_PROFILE=0
GIT_INIT_MODE="auto"
GIT_COMMIT_MODE="prompt"
DRY_RUN=0
NO_PROMPT=0
BUILD_HARNESS_SET=0
TASK_TEMPLATES_SET=0
ONBOARDING_SET=0
RELEASE_PROFILE_SET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-mode)
      PROJECT_MODE="$2"
      shift 2
      ;;
    --name)
      APP_NAME="$2"
      shift 2
      ;;
    --bundle-id)
      BUNDLE_ID="$2"
      shift 2
      ;;
    --platform)
      PLATFORM="$2"
      shift 2
      ;;
    --ui)
      UI="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    --generator-command)
      GENERATOR_COMMAND="$2"
      shift 2
      ;;
    --profile)
      PROFILE_MODE="$2"
      shift 2
      ;;
    --agent-name)
      AGENT_NAME_INPUT="$2"
      shift 2
      ;;
    --deployment-target)
      DEPLOYMENT_TARGET="$2"
      shift 2
      ;;
    --sim-name)
      SIM_NAME="$2"
      shift 2
      ;;
    --git-init)
      GIT_INIT_MODE="$2"
      shift 2
      ;;
    --git-commit)
      GIT_COMMIT_MODE="$2"
      shift 2
      ;;
    --with-build-harness)
      INSTALL_BUILD_HARNESS=1
      BUILD_HARNESS_SET=1
      shift
      ;;
    --skip-build-harness)
      INSTALL_BUILD_HARNESS=0
      BUILD_HARNESS_SET=1
      shift
      ;;
    --with-task-templates)
      INSTALL_TASK_TEMPLATES=1
      TASK_TEMPLATES_SET=1
      shift
      ;;
    --skip-task-templates)
      INSTALL_TASK_TEMPLATES=0
      TASK_TEMPLATES_SET=1
      shift
      ;;
    --with-onboarding)
      INSTALL_ONBOARDING=1
      ONBOARDING_SET=1
      shift
      ;;
    --skip-onboarding)
      INSTALL_ONBOARDING=0
      ONBOARDING_SET=1
      shift
      ;;
    --with-release-profile)
      WRITE_RELEASE_PROFILE=1
      RELEASE_PROFILE_SET=1
      shift
      ;;
    --skip-release-profile)
      WRITE_RELEASE_PROFILE=0
      RELEASE_PROFILE_SET=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-prompt)
      NO_PROMPT=1
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

prompt_if_missing() {
  local prompt="$1"
  local current="$2"
  local default="$3"

  if [[ -n "$current" ]]; then
    echo "$current"
    return 0
  fi

  if [[ $NO_PROMPT -eq 1 ]]; then
    echo "$default"
    return 0
  fi

  local input
  if [[ -n "$default" ]]; then
    read -r -p "$prompt [$default]: " input
    input="${input:-$default}"
  else
    read -r -p "$prompt: " input
  fi

  echo "$input"
}

prompt_yes_no() {
  local prompt="$1"
  local current="$2"
  local default="$3"

  if [[ $NO_PROMPT -eq 1 ]]; then
    echo "$current"
    return 0
  fi

  local hint="Y/n"
  if [[ "$default" == "0" ]]; then
    hint="y/N"
  fi

  local input
  read -r -p "$prompt [$hint]: " input
  input="$(printf '%s' "$input" | tr '[:upper:]' '[:lower:]')"

  if [[ -z "$input" ]]; then
    echo "$current"
  elif [[ "$input" == "y" || "$input" == "yes" ]]; then
    echo "1"
  else
    echo "0"
  fi
}

if [[ "$PROJECT_MODE" != "new" && "$PROJECT_MODE" != "adopt" ]]; then
  echo "Invalid --project-mode: $PROJECT_MODE" >&2
  exit 1
fi

if [[ "$PROFILE_MODE" != "generic" && "$PROFILE_MODE" != "pfe" ]]; then
  echo "Invalid --profile: $PROFILE_MODE" >&2
  exit 1
fi

if [[ "$PROFILE_MODE" == "pfe" ]]; then
  if [[ $BUILD_HARNESS_SET -eq 0 ]]; then
    INSTALL_BUILD_HARNESS=1
  fi
  if [[ $ONBOARDING_SET -eq 0 ]]; then
    INSTALL_ONBOARDING=1
  fi
  if [[ $RELEASE_PROFILE_SET -eq 0 ]]; then
    WRITE_RELEASE_PROFILE=1
  fi
fi

PROJECT_MODE="$(prompt_if_missing "Project mode (new|adopt)" "$PROJECT_MODE" "new")"
OUTPUT="$(prompt_if_missing "Project output directory" "$OUTPUT" "")"
PROFILE_MODE="$(prompt_if_missing "Profile (generic|pfe)" "$PROFILE_MODE" "generic")"

if [[ "$PROJECT_MODE" == "new" ]]; then
  APP_NAME="$(prompt_if_missing "App name" "$APP_NAME" "")"
  BUNDLE_ID="$(prompt_if_missing "Bundle id" "$BUNDLE_ID" "")"
  PLATFORM="$(prompt_if_missing "Platform (ios|ipados|macos|visionos|watchos)" "$PLATFORM" "ios")"
  UI="$(prompt_if_missing "UI (swiftui|uikit|appkit)" "$UI" "swiftui")"
else
  APP_NAME="$(prompt_if_missing "App name (for scheme and profile defaults)" "$APP_NAME" "$(basename "$OUTPUT")")"
  PLATFORM="$(prompt_if_missing "Platform for existing project" "$PLATFORM" "macos")"
fi

if [[ -z "$AGENT_NAME_INPUT" ]]; then
  AGENT_NAME_INPUT="${CODEX_AGENT_NAME:-CODEX}"
fi

if [[ $NO_PROMPT -eq 0 ]]; then
  INSTALL_BUILD_HARNESS="$(prompt_yes_no "Install Apple build harness" "$INSTALL_BUILD_HARNESS" "1")"
  INSTALL_TASK_TEMPLATES="$(prompt_yes_no "Install local task templates" "$INSTALL_TASK_TEMPLATES" "0")"
  INSTALL_ONBOARDING="$(prompt_yes_no "Install onboarding fragment" "$INSTALL_ONBOARDING" "$INSTALL_ONBOARDING")"
  WRITE_RELEASE_PROFILE="$(prompt_yes_no "Write release profile skeleton" "$WRITE_RELEASE_PROFILE" "$WRITE_RELEASE_PROFILE")"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $DRY_RUN -eq 0 ]]; then
  "$SCRIPT_DIR/doctor.sh" --project-mode "$PROJECT_MODE"
else
  echo "[dry-run] Skipping doctor execution"
fi

exec "$SCRIPT_DIR/scaffold_app.sh" \
  --project-mode "$PROJECT_MODE" \
  --name "$APP_NAME" \
  --bundle-id "$BUNDLE_ID" \
  --platform "$PLATFORM" \
  --ui "$UI" \
  --output "$OUTPUT" \
  --generator-command "$GENERATOR_COMMAND" \
  --profile "$PROFILE_MODE" \
  --agent-name "$AGENT_NAME_INPUT" \
  ${DEPLOYMENT_TARGET:+--deployment-target "$DEPLOYMENT_TARGET"} \
  ${SIM_NAME:+--sim-name "$SIM_NAME"} \
  --git-init "$GIT_INIT_MODE" \
  --git-commit "$GIT_COMMIT_MODE" \
  $([[ "$INSTALL_BUILD_HARNESS" == "1" ]] && echo --with-build-harness || echo --skip-build-harness) \
  $([[ "$INSTALL_TASK_TEMPLATES" == "1" ]] && echo --with-task-templates || echo --skip-task-templates) \
  $([[ "$INSTALL_ONBOARDING" == "1" ]] && echo --with-onboarding || echo --skip-onboarding) \
  $([[ "$WRITE_RELEASE_PROFILE" == "1" ]] && echo --with-release-profile || echo --skip-release-profile) \
  $([[ $DRY_RUN -eq 1 ]] && echo --dry-run)
