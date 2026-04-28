# Worked Examples

## Example 1: Dry-run mirror audit
- request: "Do I have any Antigravity-only skills?"
- action: run the dry-run report
- expected outcome: copy candidates, shared drift, and publication-mirror drift are reported without writing changes

## Example 2: Safe additive sync
- request: "Copy missing Antigravity skills into Codex"
- action: run `--apply` without overwrite
- expected outcome: missing skills are copied, shared drift is still surfaced for manual review

## Example 3: Publication mirror check
- request: "Is my exported skills repo current?"
- action: include the workspace root and compare it to codex canonical truth
- expected outcome: runtime residue is ignored, source drift is reported
