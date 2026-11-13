# Validation-Error Status and Media Type Example

Compares the default validation-error response (`422`, `application/json`) with a status-only
override and a status plus `application/problem+json` override.

See `docs/examples/error_status_media_type.md` for the response table. Run it offline (no Azure needed):

```bash
python -m pytest tests/test_error_status_media_type_example.py -v --no-cov
```
