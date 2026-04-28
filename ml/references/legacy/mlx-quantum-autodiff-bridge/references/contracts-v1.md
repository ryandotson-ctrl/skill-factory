# Bridge Contracts V1

## BridgeValidationV1

```json
{
  "schema": "BridgeValidationV1",
  "pass": true,
  "checks": [
    {"name": "mlx_custom_function", "passed": true, "detail": "string"}
  ],
  "missing": ["string"]
}
```

## QuantumOpSpecV1

```json
{
  "schema": "QuantumOpSpecV1",
  "n_qubits": 2,
  "ansatz_id": "string",
  "diff_method": "parameter-shift|adjoint",
  "shots": 0,
  "trainable_params": 2
}
```
