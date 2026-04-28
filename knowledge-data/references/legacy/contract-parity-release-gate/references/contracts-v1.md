# Contract Parity Gate Contracts v1

## ContractParityDomainResultV1
- `domain` (string)
- `status` (`pass` | `warning` | `blocker`)
- `evidence_ref` (string)
- `summary` (string)
- `remediation` (string)

## ContractParityGateResultV1
- `generated_at` (ISO-8601)
- `status` (`pass` | `warning` | `blocker`)
- `required_domains` (string[])
- `domain_results` (`ContractParityDomainResultV1[]`)
- `blocking_domains` (string[])
- `release_recommendation` (string)
- `assumptions` (string[])

## Default Gate Policy
1. Missing required domain -> `blocker`
2. Any blocker domain -> `blocker`
3. No blockers and at least one warning -> `warning`
4. All pass -> `pass`
