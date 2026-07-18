# E2E Test App

The end-to-end test function app for `azure-functions-validation`. Unlike the other
examples, this app is not a feature walkthrough — it is the minimal app that
[`.github/workflows/e2e-azure.yml`](../../.github/workflows/e2e-azure.yml) deploys to a
temporary Azure Functions instance to verify the package works on real infrastructure.

The app lives in [`function_app.py`](function_app.py).

## Endpoints

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness probe returning `{"status": "ok"}` |
| `POST` | `/api/items` | Validated create via `@validate_http` (`CreateItemRequest` → `ItemResponse`) |

## Run locally

```bash
cd examples/e2e_app
func start
```

Then, in another terminal:

```bash
curl -s http://localhost:7071/api/health
# {"status": "ok"}

curl -s -X POST http://localhost:7071/api/items \
  -H "Content-Type: application/json" \
  -d '{"name": "widget", "quantity": 3}'
# {"id": 1, "name": "widget", "quantity": 3}
```

An invalid body returns the standard `422` validation envelope:

```bash
curl -s -X POST http://localhost:7071/api/items \
  -H "Content-Type: application/json" \
  -d '{"name": "", "quantity": 0}'
# {"detail": [...]}
```
