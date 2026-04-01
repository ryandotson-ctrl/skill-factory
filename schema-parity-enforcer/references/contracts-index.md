# Contract Index Guidance

Use this index when `docs/contracts/` is present in a workspace.

## Domains
1. `chat_runtime`
2. `search_grounding`
3. `rag`
4. `model_lifecycle`
5. `training_pipeline`
6. `filesystem_actions`
7. `sessions`
8. `workspaces`
9. `model_catalog`
10. `browser_automation`

## Expected Output
Emit per-domain status:
- `pass`
- `warning`
- `blocker`

Each domain result should include:
- `contract_file`
- `parity_gate`
- `schema_evidence`
- `remediation`
