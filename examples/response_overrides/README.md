# Response Overrides Example

Return a non-default success status and a custom header with `ResponseSpec` while `response_model`
validation and serialization still run.

- `create_item`: `201` plus `Location`; the declared model filters undeclared fields
- `accept_item`: inherits the decorator's `202`, adds a header
- `broken_item`: wrong content with an override is still the sanitized `500`

See `docs/examples/response_overrides.md` for the exact status/headers/body. Run it offline (no Azure needed):

```bash
python -m pytest tests/test_response_overrides_example.py -v --no-cov
```
