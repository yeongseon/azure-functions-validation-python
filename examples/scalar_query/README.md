# Scalar Query Validation Example

Opt-in `query_params` validation for a few scalar or flat-list query inputs, without a query `BaseModel`.

- Typed, keyword-only injection (`int`, `date`, `StrEnum`, `list[str]`)
- Aliased wire name (`page-size`) reported in the `422` `loc`
- `undeclared_query` shows nothing is validated without the declaration

See `docs/examples/scalar_query.md` for the behavior table. Run it offline (no Azure needed):

```bash
python -m pytest tests/test_scalar_query_example.py -v --no-cov
```
