# Receipt Templates

## Default Template
```text
UnderstandingReceiptV1
- why_this_works:
- what_could_break:
- how_to_debug:
- unknowns:
```

## Good Receipt Characteristics
- Mention mechanism, not vibes.
- Mention at least one realistic failure mode.
- Mention the first place to look when debugging.
- Name uncertainty explicitly when confidence is partial.

## Prompting Aids
- "What changed in the causal path?"
- "Which invariant is now protected?"
- "What symptom would tell us this assumption was wrong?"
- "Where would you start debugging at 3 a.m.?"

## Common Receipts
- Feature change:
  - why the design handles the requested path
  - what regressions are most likely
- Bug fix:
  - what root cause was addressed
  - how to tell if the bug reappeared
- Incident:
  - why the mitigation restored service
  - what durable fix is still missing
