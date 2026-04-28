#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: scaffold_app.sh [options]

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
  --regenerate
  --dry-run
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
REGENERATE=0
INSTALL_BUILD_HARNESS=1
INSTALL_TASK_TEMPLATES=0
INSTALL_ONBOARDING=0
WRITE_RELEASE_PROFILE=0
GIT_INIT_MODE="auto"
GIT_COMMIT_MODE="prompt"
DRY_RUN=0
PREEXISTING_GIT_REPO=0
PREEXISTING_DIRTY=0

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
      shift
      ;;
    --skip-build-harness)
      INSTALL_BUILD_HARNESS=0
      shift
      ;;
    --with-task-templates)
      INSTALL_TASK_TEMPLATES=1
      shift
      ;;
    --skip-task-templates)
      INSTALL_TASK_TEMPLATES=0
      shift
      ;;
    --with-onboarding)
      INSTALL_ONBOARDING=1
      shift
      ;;
    --skip-onboarding)
      INSTALL_ONBOARDING=0
      shift
      ;;
    --with-release-profile)
      WRITE_RELEASE_PROFILE=1
      shift
      ;;
    --skip-release-profile)
      WRITE_RELEASE_PROFILE=0
      shift
      ;;
    --regenerate)
      REGENERATE=1
      shift
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

if [[ "$PROJECT_MODE" != "new" && "$PROJECT_MODE" != "adopt" ]]; then
  echo "Invalid --project-mode: $PROJECT_MODE" >&2
  exit 1
fi

if [[ "$PROFILE_MODE" != "generic" && "$PROFILE_MODE" != "pfe" ]]; then
  echo "Invalid --profile: $PROFILE_MODE" >&2
  exit 1
fi

if [[ "$GIT_INIT_MODE" != "auto" && "$GIT_INIT_MODE" != "never" ]]; then
  echo "Invalid --git-init: $GIT_INIT_MODE" >&2
  exit 1
fi

if [[ "$GIT_COMMIT_MODE" != "prompt" && "$GIT_COMMIT_MODE" != "always" && "$GIT_COMMIT_MODE" != "never" ]]; then
  echo "Invalid --git-commit: $GIT_COMMIT_MODE" >&2
  exit 1
fi

if [[ -z "$OUTPUT" ]]; then
  echo "Missing --output" >&2
  usage
  exit 1
fi

if [[ -d "$OUTPUT" ]] && git -C "$OUTPUT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  PREEXISTING_GIT_REPO=1
  if [[ -n "$(git -C "$OUTPUT" status --porcelain 2>/dev/null)" ]]; then
    PREEXISTING_DIRTY=1
  fi
fi

default_deployment_target() {
  case "$1" in
    ios|ipados)
      echo "18.0"
      ;;
    macos)
      echo "15.4"
      ;;
    visionos)
      echo "2.4"
      ;;
    watchos)
      echo "11.0"
      ;;
    *)
      echo ""
      ;;
  esac
}

default_sim_name() {
  case "$1" in
    ios)
      echo "auto"
      ;;
    ipados)
      echo "auto"
      ;;
    visionos)
      echo "auto"
      ;;
    watchos)
      echo "auto"
      ;;
    *)
      echo ""
      ;;
  esac
}

template_key_for() {
  local platform="$1"
  local ui="$2"
  case "$platform" in
    ios|ipados)
      echo "ios-$ui"
      ;;
    macos)
      echo "macos-$ui"
      ;;
    visionos)
      echo "visionos-$ui"
      ;;
    watchos)
      echo "watchos-$ui"
      ;;
  esac
}

if [[ -z "$APP_NAME" ]]; then
  APP_NAME="$(basename "$OUTPUT")"
fi

if [[ -z "$AGENT_NAME_INPUT" ]]; then
  AGENT_NAME_INPUT="${CODEX_AGENT_NAME:-CODEX}"
fi

if [[ -z "$DEPLOYMENT_TARGET" ]]; then
  DEPLOYMENT_TARGET="$(default_deployment_target "$PLATFORM")"
fi

if [[ -z "$SIM_NAME" ]]; then
  SIM_NAME="$(default_sim_name "$PLATFORM")"
fi

case "$PLATFORM" in
  ios|ipados|macos|visionos|watchos)
    ;;
  *)
    echo "Invalid --platform: $PLATFORM" >&2
    exit 1
    ;;
esac

case "$UI" in
  swiftui)
    ;;
  uikit)
    if [[ "$PLATFORM" != "ios" && "$PLATFORM" != "ipados" ]]; then
      echo "UIKit is only valid for iOS and iPadOS." >&2
      exit 1
    fi
    ;;
  appkit)
    if [[ "$PLATFORM" != "macos" ]]; then
      echo "AppKit is only valid for macOS." >&2
      exit 1
    fi
    ;;
  *)
    echo "Invalid --ui: $UI" >&2
    exit 1
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEMPLATE_ROOT="$SCRIPT_DIR/../assets/xcodegen"
RENDER="$SCRIPT_DIR/render_template.py"
HARNESS_INSTALLER="$SKILLS_ROOT/xcode-build-harness-installer/scripts/install.sh"
TASK_INSTALLER="$SCRIPT_DIR/install_task_templates.sh"
ONBOARDING_INSTALLER="$SCRIPT_DIR/install_onboarding_fragment.sh"
PROFILE_WRITER="$SCRIPT_DIR/write_release_profile.py"
TEMPLATE_DIR="$TEMPLATE_ROOT/$(template_key_for "$PLATFORM" "$UI")"

if [[ "$PROJECT_MODE" == "new" ]]; then
  if [[ -z "$BUNDLE_ID" ]]; then
    echo "Missing --bundle-id for new projects" >&2
    exit 1
  fi
  if [[ ! -d "$TEMPLATE_DIR" ]]; then
    echo "Template not found: $TEMPLATE_DIR" >&2
    exit 1
  fi
fi

existing_project=0
if [[ -d "$OUTPUT" ]]; then
  if ls "$OUTPUT"/*.xcodeproj >/dev/null 2>&1 || ls "$OUTPUT"/*.xcworkspace >/dev/null 2>&1; then
    existing_project=1
  fi
fi

if [[ "$PROJECT_MODE" == "new" && -e "$OUTPUT" && -n "$(ls -A "$OUTPUT" 2>/dev/null)" ]]; then
  if [[ $existing_project -eq 1 && $REGENERATE -eq 0 ]]; then
    echo "Existing Xcode project detected in $OUTPUT. Skipping regeneration." >&2
  else
    echo "Output directory exists and is not empty: $OUTPUT" >&2
    if [[ $existing_project -eq 1 ]]; then
      echo "Use --regenerate to refresh an existing project in place." >&2
    else
      echo "Use an empty output directory to generate a new project." >&2
    fi
    exit 1
  fi
fi

run_generator() {
  if [[ -z "$GENERATOR_COMMAND" ]]; then
    return 0
  fi
  echo "Running generator: $GENERATOR_COMMAND"
  (cd "$OUTPUT" && eval "$GENERATOR_COMMAND")
}

install_build_harness() {
  local harness_mode="install"
  if [[ "$PROJECT_MODE" == "adopt" || $existing_project -eq 1 || $REGENERATE -eq 1 ]]; then
    harness_mode="upgrade"
  fi
  "$HARNESS_INSTALLER" \
    --project-dir "$OUTPUT" \
    --app-name "$APP_NAME" \
    --platform "$PLATFORM" \
    --mode "$harness_mode" \
    ${SIM_NAME:+--sim-name "$SIM_NAME"} \
    $([[ $DRY_RUN -eq 1 ]] && echo --dry-run)
}

install_task_templates() {
  local mode="install"
  if [[ "$PROJECT_MODE" == "adopt" ]]; then
    mode="upgrade"
  fi
  "$TASK_INSTALLER" \
    --project-dir "$OUTPUT" \
    --mode "$mode" \
    $([[ $DRY_RUN -eq 1 ]] && echo --dry-run)
}

install_onboarding_fragment() {
  local mode="install"
  if [[ "$PROJECT_MODE" == "adopt" ]]; then
    mode="upgrade"
  fi
  "$ONBOARDING_INSTALLER" \
    --project-dir "$OUTPUT" \
    --profile "$PROFILE_MODE" \
    --mode "$mode" \
    $([[ $DRY_RUN -eq 1 ]] && echo --dry-run)
}

write_release_profile() {
  python3 "$PROFILE_WRITER" \
    --project-dir "$OUTPUT" \
    --app-name "$APP_NAME" \
    --bundle-id "$BUNDLE_ID" \
    --platform "$PLATFORM" \
    --generator-command "$GENERATOR_COMMAND" \
    $([[ $DRY_RUN -eq 1 ]] && echo --dry-run)
}

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[dry-run] mode: $PROJECT_MODE"
  echo "[dry-run] profile: $PROFILE_MODE"
  echo "[dry-run] output: $OUTPUT"
  echo "[dry-run] platform/ui: $PLATFORM / $UI"
  if [[ "$PROJECT_MODE" == "new" ]]; then
    echo "[dry-run] would scaffold template: $TEMPLATE_DIR"
    echo "[dry-run] would run generator: $GENERATOR_COMMAND"
  else
    echo "[dry-run] adopt existing project without regeneration"
  fi
else
  mkdir -p "$OUTPUT"
  if [[ "$PROJECT_MODE" == "new" && ($existing_project -eq 0 || $REGENERATE -eq 1) ]]; then
    python3 "$RENDER" \
      --src "$TEMPLATE_DIR" \
      --dst "$OUTPUT" \
      --var APP_NAME="$APP_NAME" \
      --var BUNDLE_ID="$BUNDLE_ID" \
      --var DEPLOYMENT_TARGET="$DEPLOYMENT_TARGET"
    run_generator
  fi
fi

if [[ $INSTALL_BUILD_HARNESS -eq 1 ]]; then
  install_build_harness
fi

if [[ $INSTALL_TASK_TEMPLATES -eq 1 ]]; then
  install_task_templates
fi

if [[ $INSTALL_ONBOARDING -eq 1 ]]; then
  install_onboarding_fragment
fi

if [[ $WRITE_RELEASE_PROFILE -eq 1 ]]; then
  write_release_profile
fi

if [[ $DRY_RUN -eq 0 && "$GIT_INIT_MODE" == "auto" && $PREEXISTING_GIT_REPO -eq 0 && ! -d "$OUTPUT/.git" ]]; then
  git -C "$OUTPUT" init >/dev/null
fi

if [[ $DRY_RUN -eq 0 && "$GIT_COMMIT_MODE" != "never" && $PREEXISTING_DIRTY -eq 0 ]]; then
  if git -C "$OUTPUT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$OUTPUT" add .
    if [[ -n "$(git -C "$OUTPUT" diff --cached --name-only)" ]]; then
      if [[ "$GIT_COMMIT_MODE" == "always" ]]; then
        git -C "$OUTPUT" commit -m "chore: bootstrap Apple project"
      else
        echo "Git changes staged. Run this to commit:"
        echo "  git -C \"$OUTPUT\" commit -m \"chore: bootstrap Apple project\""
      fi
    fi
  fi
fi

echo ""
echo "Bootstrap receipt"
echo "- mode: $PROJECT_MODE"
echo "- platform: $PLATFORM"
echo "- ui: $UI"
echo "- project root: $OUTPUT"
echo "- profile: $PROFILE_MODE"
echo "- build harness: $([[ $INSTALL_BUILD_HARNESS -eq 1 ]] && echo installed || echo skipped)"
echo "- task templates: $([[ $INSTALL_TASK_TEMPLATES -eq 1 ]] && echo installed || echo skipped)"
echo "- onboarding: $([[ $INSTALL_ONBOARDING -eq 1 ]] && echo installed || echo skipped)"
echo "- release profile: $([[ $WRITE_RELEASE_PROFILE -eq 1 ]] && echo written || echo skipped)"
echo ""
echo "Next commands"
if [[ $INSTALL_BUILD_HARNESS -eq 1 ]]; then
  echo "  make diagnose"
  echo "  make agent-verify"
fi
if [[ $INSTALL_TASK_TEMPLATES -eq 1 ]]; then
  echo "  scripts/task.sh status"
fi
if [[ $WRITE_RELEASE_PROFILE -eq 1 ]]; then
  echo "  python3 \"\$CODEX_HOME/skills/apple-ecosystem-release-operator/scripts/apple_release_operator.py\" preflight --profile \"$OUTPUT/release/apple_release_profile.yaml\""
fi
