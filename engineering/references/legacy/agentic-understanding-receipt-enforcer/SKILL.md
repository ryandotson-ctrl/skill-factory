---
name: agentic-understanding-receipt-enforcer
description: Portable explain-as-you-go discipline for agentic engineering. Use when implementation, debugging, review, or incident work should produce short receipts proving why the change works, what could break, and how to debug it without turning the task into a lecture.
---

# Agentic Understanding Receipt Enforcer

Produce short receipts that prove understanding at the moments where speed usually hides risk.

Read `references/receipt-templates.md` for reusable receipt shapes and debugging prompts.

## Workflow
1. Emit `UnderstandingReceiptV1` with:
   - `why_this_works`
   - `what_could_break`
   - `how_to_debug`
   - `unknowns`
2. Keep receipts short and specific. Prefer concrete mechanisms over generic reassurance.
3. Require a receipt at these checkpoints:
   - before medium/high-risk implementation
   - after a non-trivial bug fix
   - before merge or release for risky work
   - after an incident mitigation
4. If the explanation is thin or hand-wavy, slow down and route to the missing specialist:
   - `$agentic-design-contract-architect`
   - `$agentic-performance-reality-guardian`
   - `$agentic-incident-triage-commander`
5. Distinguish known unknowns from guesses. Uncertainty is acceptable; fake certainty is not.

## Non-Negotiable Rules
- Do not turn receipts into long tutorials.
- Do not restate the diff. Explain causality, risk, and debugging entrypoints.
- If you cannot explain a change clearly, do not claim to understand it.
