# Body Policies Example

Shows the opt-in `require_json_content_type` (`415`) and `max_body_bytes` (`413`) policies on a
strict handler next to a default handler that accepts the same requests. These are application-level
checks and do not replace ingress, WAF or hosting limits.

See `docs/examples/body_policies.md`. Run it offline (no Azure needed):

```bash
python -m pytest tests/test_body_policies_example.py -v --no-cov
```
