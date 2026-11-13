# Validation Aggregation Example

Compares the default fail-fast validation (first failing source only) with
`aggregate_validation_errors=True` (body and query errors together, in order) for a request
whose body and query are both invalid.

See `docs/examples/validation_aggregation.md`. Run it offline (no Azure needed):

```bash
python -m pytest tests/test_validation_aggregation_example.py -v --no-cov
```
