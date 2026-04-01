# Handoff QA Checklist

Use this to close the gap between design intent and implementation quality.

## Handoff Requirements
- component API expectations
- variants and states
- token usage expectations
- responsive rules and breakpoints
- motion and reduced-motion expectations

## QA Checklist
- hierarchy still obvious at all supported sizes
- spacing rhythm matches the token system
- keyboard and focus behavior are visible and usable
- contrast remains acceptable on all key surfaces
- loading, empty, error, success, offline, and blocked states exist
- no flicker or layout shift during streaming or async updates

## Regression Risks
- accidental one-off spacing values
- glass reducing readability
- ambiguous destructive controls
- hidden verification states for async work
- drift between web and platform translation rules

## Do Not Regress
- primary content hierarchy
- primary action clarity
- trust cues
- state coverage
- reduced-motion behavior
