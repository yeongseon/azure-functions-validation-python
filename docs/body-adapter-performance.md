# Static body adapter reuse

The default Pydantic decorator path prepares one body `TypeAdapter` during
decoration. The adapter is private to that decorator instance and reused only
for the identical model object. Direct adapter calls and explicitly supplied
custom adapters keep their existing `parse_body(req, model)` contract. Query
validation continues to use `model_validate`; no global cache is introduced.
Failed preparation retains the prior request-time error behavior. Dynamic
model rebuilds after decoration are not a static contract and require redecorating.

Reproduce with `hatch run python scripts/benchmark_body_adapter.py` after environment
setup. Five repeats of 10,000 validations compare construction plus validation
against a prebuilt adapter, reporting the minimum per-call time. Local Python
3.11.15 / Pydantic 2.14.1 observations:

| Annotation | Construct each call | Reuse | Saved per validation |
| --- | ---: | ---: | ---: |
| Small model | 5.638 μs | 0.728 μs | 4.910 μs |
| Nested model | 6.223 μs | 1.225 μs | 4.998 μs |
| Small-or-nested union | 75.183 μs | 1.000 μs | 74.183 μs |

These are adapter-only microbenchmarks, not HTTP latency promises. The cost moves
to decoration and retains one adapter/model reference per default decorator.
Custom adapters receive no new required keyword arguments or mutable shared cache.
