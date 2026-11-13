# Custom Adapter Conformance Example

`adapter.py` is a tiny, non-Pydantic `ValidationAdapter` implementing the full public protocol,
including `serialize_response()`. `tests/test_custom_adapter_example.py` runs it through the shipped
`AdapterConformanceTests` (success) and runs deliberately broken adapters through the same suite
(failure). It is not a deployable Functions app, so it has no `host.json`.

See `docs/examples/custom_adapter.md`, including what conformance does not certify. Run it offline
(no Azure needed):

```bash
python -m pytest tests/test_custom_adapter_example.py -v --no-cov
```
