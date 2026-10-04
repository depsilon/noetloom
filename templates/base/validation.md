# Validation

Replace the failing initial check with real behavior checks and complete input patterns.

<!-- noetloom:validation -->
```json
{
  "version": 1,
  "checks": [{
    "id": "application",
    "command": ["{python}", "-c", "raise SystemExit('Replace the bootstrap check with meaningful application tests before completion')"],
    "cwd": ".",
    "inputs": ["AGENTS.md"],
    "timeout_seconds": 30
  }]
}
```
