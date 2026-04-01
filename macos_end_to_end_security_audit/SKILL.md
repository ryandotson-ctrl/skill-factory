---
name: macos_end_to_end_security_audit
description: Apple-level, read-only macOS security + privacy audit (processes, listeners,
  established connections, persistence, background items/login items, browser policy/extensions,
  shares, trust store, MDM/profiles, firewall, proxy/DNS). Console-first output; PDF
  is opt-in.
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# macOS End-to-End Security Audit (Read-Only)

This skill runs a defensive, non-destructive audit.

- Default: prints a redacted **console summary** with findings + actionable next steps.
- Optional: generate a redacted **PDF** only when you explicitly request it.

## Safety + privacy

- **Non-destructive**: does not delete files, unload services, or change settings.
- **Privacy-aware**: defaults to `--privacy strict` and prints a redacted summary by default.
- If you generate a PDF, treat it like a password-manager export (system inventory).

## Modes (defaults)

- `--format {text,json}`
  - `text` (default): prints a redacted console summary with findings + next steps.
  - `json`: prints a **sanitized JSON object** (good for automation + diffing).

- `--depth {standard,deep}`
  - `standard` (default): fast, high-signal checks.
  - `deep`: adds heavier checks (more signing assessments, more process/connection rows).

- `--privacy {strict,balanced,forensics}`
  - `strict` (default): redacts home paths, tokens/keys, and remote endpoints in connection tables.
  - `balanced`: keeps hostnames/endpoints where possible, still redacts tokens/keys.
  - `forensics`: minimal redaction (still redacts obvious secrets). Use only when you will store/share the PDF securely.

- `--max-rows N`
  - Limits large tables (processes, connections, extensions) to N rows (default: 60).

- `--recent-apps-days N`
  - Scans `/Applications` and `~/Applications` for recently modified `.app` bundles (default: `14` in `standard`, `60` in `deep`).

- `--recent-apps-max N`
  - Max recent apps to assess for trust/quarantine signals (default: `20` in `standard`, `60` in `deep`).

- `--diff-last`
  - Reads the most recent history snapshot (if present) and prints **what changed since last run** first.
  - Read-only: does not write snapshots unless you also pass `--history`.

- `--tcc-recent-log-minutes N`
  - Optional: if automatic TCC DB inspection is blocked, sample recent TCC events from unified logging (best-effort).

- `--pdf`
  - Off by default. When set, also generates a PDF report.

- `--output-pdf /path/to/report.pdf`
  - Write the PDF to an explicit file path (implies `--pdf`).

- `--output-dir /path/to/dir`
  - Where to write the PDF when `--pdf` is set.
  - Default: `~/Library/Application Support/macos_end_to_end_security_audit/reports/` (private).

- `--history / --no-history`
  - Default: `--no-history` (writes no snapshots).
  - If enabled, writes a small sanitized JSON snapshot for diffing to:
    `~/Library/Application Support/macos_end_to_end_security_audit/history/` (0700 dir, 0600 files)

## What we collect (high-level)

1. OS integrity + platform protections (SIP, Gatekeeper, FileVault, system extensions/kexts, best-effort Lockdown Mode)
2. Persistence + background execution (LaunchAgents/Daemons, launchd status, Background Items/Login Items via BTM)
3. Network surface + exfil paths (listeners, established connection samples, proxy/DNS/hosts, VPN services)
4. Privacy controls (best-effort TCC grants; graceful fallback if blocked)
5. Trust & MITM signals (custom trust settings)
6. Sharing / local data exposure (share points + guest access flags)
7. Browser attack surface (extensions + external/forced extension artifacts + native messaging hosts)
8. Untrusted installs detection (recent `.app` bundles: ad-hoc/unsigned, Gatekeeper rejects, quarantine-bypass signals)

## Workspace Goal Alignment
When auditing a Mac that is actively used for local-first AI product development and testing,
prioritize evidence that helps separate expected developer tooling from suspicious behavior:

- Local AI runtime processes, helper workers, model downloaders, browser automation, and local backend listeners.
- Tools with sensitive privacy grants such as Terminal, Python, Node, browsers, automation helpers,
  and Xcode-adjacent workflows.
- Recently modified desktop app bundles, launchers, helper tools, and sidecar utilities tied to local development.
- Data exposure paths around model caches, local databases, browser profiles, automation artifacts,
  and other workspace-adjacent stores.
- Any persistence or network surface that does not clearly map back to the active local AI workflow,
  because that is where false negatives tend to hide in development-heavy Macs.

## How to run

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/macos_end_to_end_security_audit/scripts/audit_and_report.py
```

Examples:

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/macos_end_to_end_security_audit/scripts/audit_and_report.py --privacy balanced
python3 ${CODEX_HOME:-~/.codex}/skills/macos_end_to_end_security_audit/scripts/audit_and_report.py --depth deep --privacy forensics --no-history
python3 ${CODEX_HOME:-~/.codex}/skills/macos_end_to_end_security_audit/scripts/audit_and_report.py --format json
python3 ${CODEX_HOME:-~/.codex}/skills/macos_end_to_end_security_audit/scripts/audit_and_report.py --diff-last
python3 ${CODEX_HOME:-~/.codex}/skills/macos_end_to_end_security_audit/scripts/audit_and_report.py --pdf
python3 ${CODEX_HOME:-~/.codex}/skills/macos_end_to_end_security_audit/scripts/audit_and_report.py --pdf --output-dir ~/Desktop --max-rows 120
python3 ${CODEX_HOME:-~/.codex}/skills/macos_end_to_end_security_audit/scripts/audit_and_report.py --output-pdf ~/Desktop/security_audit_report.pdf
```

## Manual verification (keylogger / privacy permissions)

Some automation is blocked by macOS protections without additional permissions.
For maximum confidence, review these pages in **System Settings -> Privacy & Security**:

- Input Monitoring
- Accessibility
- Screen Recording
- Full Disk Access
- Automation (Apple Events)
- Microphone
- Camera

Only expected apps should be enabled.

## Notes

- `spctl`/`codesign` assessment is used to *highlight* persistence executables that are unsigned/rejected. Developer tools (Homebrew, venv Python, Node) may show weaker trust signals; those are usually “review” rather than “malware”.
- If a check is blocked (permissions), the report will say **unknown (permission blocked)** and give manual steps.

## Closed beta / quarantine bypass mini-runbook

If you install a closed beta and have to do anything like clearing quarantine attributes (for example `xattr -cr`), treat it as higher risk and confirm:

- The app is not running from `/Volumes/...` (DMG-mounted path).
- Gatekeeper assessment (`spctl`) is **accepted** for the `.app` bundle.
- `codesign` is not `unsigned` or `adhoc` for an app living in `/Applications`.
- Privacy permissions (TCC) grants are expected: Input Monitoring, Accessibility, Screen Recording, Full Disk Access, Automation, Microphone, Camera.

This skill’s “Recent app installs/modifications” section is designed to flag these situations quickly.
