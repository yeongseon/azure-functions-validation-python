# Header Alias Precedence Example

A header field that accepts two wire names through `AliasChoices`: the alias listed first wins when a
client sends both, whatever the request header order, and header names match case-insensitively.

See `docs/examples/header_alias_precedence.md`. Run it offline (no Azure needed):

```bash
python -m pytest tests/test_header_alias_precedence_example.py -v --no-cov
```
