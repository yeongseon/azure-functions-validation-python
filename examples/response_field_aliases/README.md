# Response Field Aliases Example

Demonstrates serialized Pydantic field aliases in HTTP responses under `azure-functions-validation`.

By default, `@validate_http(response_model=...)` uses `response_by_alias=True`, emitting declared `Field(alias=...)` and `Field(serialization_alias=...)` names on the wire. Setting `response_by_alias=False` emits Python field names instead.

See `docs/examples/response_field_aliases.md`. Run it offline (no Azure needed):

```bash
python -m pytest tests/test_response_field_aliases_example.py -v --no-cov
```
