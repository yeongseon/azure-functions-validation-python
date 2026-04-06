# Deployment Guide
This guide walks through deploying the validation examples to Azure Functions and verifying request/response behavior end to end. It includes resource provisioning, publish, and endpoint verification for three examples: `hello_validation`, `profile_validation`, and `crud_api`. For package setup and local development, see [`getting-started.md`](./getting-started.md). Outputs are representative examples, not guaranteed byte-for-byte.

## Prerequisites
| Requirement | Minimum | Notes |
|---|---|---|
| Azure subscription | Active | Use `<YOUR_SUBSCRIPTION_ID>` |
| Azure CLI (`az`) | Current | `az --version` |
| Azure Functions Core Tools (`func`) | v4 | `func --version` |
| Python | 3.10+ | Deploy runtime shown is Python 3.11 |
| Storage Account | StorageV2 | Required by Function App |
| pip packages | Installable | See updated `requirements.txt` |

After preparing your app with the three example routes, install dependencies:
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```
Representative output:
```bash
Requirement already satisfied: pip in ./.venv/lib/python3.11/site-packages (25.0)
Collecting azure-functions
Collecting azure-functions-validation
Collecting pydantic
Successfully installed azure-functions-1.21.0 azure-functions-validation-0.6.0 pydantic-2.11.0
```

## Provision Azure resources
```bash
az account set --subscription <YOUR_SUBSCRIPTION_ID>
az group create --name <YOUR_RESOURCE_GROUP> --location eastus
```
Representative output:
```json
{"name":"<YOUR_RESOURCE_GROUP>","location":"eastus","properties":{"provisioningState":"Succeeded"}}
```
```bash
az storage account create \
  --name <YOUR_STORAGE_ACCOUNT> \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2
```
Representative output:
```json
{"name":"<YOUR_STORAGE_ACCOUNT>","kind":"StorageV2","provisioningState":"Succeeded"}
```
```bash
az functionapp create \
  --name <YOUR_FUNCTION_APP_NAME> \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --storage-account <YOUR_STORAGE_ACCOUNT> \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4
```
Representative output:
```json
{"name":"<YOUR_FUNCTION_APP_NAME>","defaultHostName":"<YOUR_FUNCTION_APP_NAME>.azurewebsites.net","provisioningState":"Succeeded","state":"Running"}
```

## Configure app settings
```bash
az storage account show-connection-string \
  --name <YOUR_STORAGE_ACCOUNT> \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --query connectionString \
  --output tsv
```
Representative output:
```text
<YOUR_STORAGE_CONNECTION_STRING>
```
```bash
az functionapp config appsettings set \
  --name <YOUR_FUNCTION_APP_NAME> \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --settings AzureWebJobsStorage="<YOUR_STORAGE_CONNECTION_STRING>" FUNCTIONS_WORKER_RUNTIME="python"
```
Representative output:
```json
[{"name":"AzureWebJobsStorage","slotSetting":false,"value":""},{"name":"FUNCTIONS_WORKER_RUNTIME","slotSetting":false,"value":"python"}]
```
Values may appear redacted in recent Azure CLI versions.

## Publish
```bash
func azure functionapp publish <YOUR_FUNCTION_APP_NAME>
```
Representative output:
```text
Getting site publishing info...
[2026-03-12T09:10:31.021Z] Starting the function app deployment...
Uploading package...
Deployment completed successfully.
Syncing triggers...
Functions in <YOUR_FUNCTION_APP_NAME>:
    hello_validation - [httpTrigger]
        Invoke url: https://<YOUR_FUNCTION_APP_NAME>.azurewebsites.net/api/hello_validation
    get_profile - [httpTrigger]
        Invoke url: https://<YOUR_FUNCTION_APP_NAME>.azurewebsites.net/api/users/{user_id}
    list_tasks - [httpTrigger]
        Invoke url: https://<YOUR_FUNCTION_APP_NAME>.azurewebsites.net/api/tasks
    get_task - [httpTrigger]
        Invoke url: https://<YOUR_FUNCTION_APP_NAME>.azurewebsites.net/api/tasks/{task_id}
    create_task - [httpTrigger]
        Invoke url: https://<YOUR_FUNCTION_APP_NAME>.azurewebsites.net/api/tasks
    update_task - [httpTrigger]
        Invoke url: https://<YOUR_FUNCTION_APP_NAME>.azurewebsites.net/api/tasks/{task_id}
    delete_task - [httpTrigger]
        Invoke url: https://<YOUR_FUNCTION_APP_NAME>.azurewebsites.net/api/tasks/{task_id}
Deployment successful.
```

## Verify examples
```bash
export BASE_URL="https://<YOUR_FUNCTION_APP_NAME>.azurewebsites.net"
```

### Example 1: `hello_validation`
#### `POST /api/hello_validation` (valid body)
```bash
curl -i -s -X POST "$BASE_URL/api/hello_validation" \
  -H "Content-Type: application/json" \
  -d '{"name":"Azure"}'
```
Representative response:
```text
HTTP/1.1 200 OK
Content-Type: application/json

{"message":"Hello Azure"}
```

#### `POST /api/hello_validation` (missing required field)
```bash
curl -i -s -X POST "$BASE_URL/api/hello_validation" \
  -H "Content-Type: application/json" \
  -d '{}'
```
Representative response:
```text
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"detail":[{"loc":["name"],"msg":"Field required","type":"missing"}]}
```

#### `POST /api/hello_validation` (invalid JSON)
```bash
curl -i -s -X POST "$BASE_URL/api/hello_validation" \
  -H "Content-Type: application/json" \
  -d '{"name":"Azure"'
```
Representative response:
```text
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"detail":[{"loc":[],"msg":"Invalid JSON","type":"value_error"}]}
```

### Example 2: `profile_validation`
#### `GET /api/users/42?verbose=true` (valid path, query, header)
```bash
curl -i -s "$BASE_URL/api/users/42?verbose=true" \
  -H "x-request-id: req-001"
```
Representative response:
```text
HTTP/1.1 200 OK
Content-Type: application/json

{"user_id":42,"view":"detailed","request_id":"req-001"}
```

#### `GET /api/users/0` (path constraint violation)
```bash
curl -i -s "$BASE_URL/api/users/0?verbose=true" \
  -H "x-request-id: req-001"
```
Representative response:
```text
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"detail":[{"loc":["user_id"],"msg":"Input should be greater than or equal to 1","type":"greater_than_equal"}]}
```

#### `GET /api/users/42` (missing required header)
```bash
curl -i -s "$BASE_URL/api/users/42?verbose=true"
```
Representative response:
```text
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"detail":[{"loc":["x-request-id"],"msg":"Field required","type":"missing"}]}
```

### Example 3: `crud_api`
This sample starts with three pre-seeded tasks and `_NEXT_ID = 4`:
Representative response:
```json
[
  {"id":1,"title":"Write docs","description":"Add examples","priority":2,"done":false},
  {"id":2,"title":"Fix bug #42","description":"","priority":5,"done":true},
  {"id":3,"title":"Add tests","description":"Cover edge cases","priority":3,"done":false}
]
```

#### `GET /api/tasks` (list tasks)
```bash
curl -i -s "$BASE_URL/api/tasks"
```
Representative response:
```text
HTTP/1.1 200 OK
Content-Type: application/json

[{"id":1,"title":"Write docs","description":"Add examples","priority":2,"done":false},{"id":2,"title":"Fix bug #42","description":"","priority":5,"done":true},{"id":3,"title":"Add tests","description":"Cover edge cases","priority":3,"done":false}]
```

#### `POST /api/tasks` (create task)
`TaskCreateRequest` constraints:
- `title`: `min_length=1`, `max_length=200`
- `description`: default `""`, `max_length=1000`
- `priority`: `ge=1`, `le=5`, default `3`
```bash
curl -i -s -X POST "$BASE_URL/api/tasks" \
  -H "Content-Type: application/json" \
  -d '{"title":"Deploy app","priority":2}'
```
Representative response:
```text
HTTP/1.1 200 OK
Content-Type: application/json

{"id":4,"title":"Deploy app","description":"","priority":2,"done":false}
```

#### `GET /api/tasks/4` (get task)
```bash
curl -i -s "$BASE_URL/api/tasks/4"
```
Representative response:
```text
HTTP/1.1 200 OK
Content-Type: application/json

{"id":4,"title":"Deploy app","description":"","priority":2,"done":false}
```

#### `PATCH /api/tasks/4` (partial update)
```bash
curl -i -s -X PATCH "$BASE_URL/api/tasks/4" \
  -H "Content-Type: application/json" \
  -d '{"done":true}'
```
Representative response:
```text
HTTP/1.1 200 OK
Content-Type: application/json

{"id":4,"title":"Deploy app","description":"","priority":2,"done":true}
```

#### `DELETE /api/tasks/4` (no content)
```bash
curl -i -s -X DELETE "$BASE_URL/api/tasks/4"
```
Representative response:
```text
HTTP/1.1 204 No Content
```

#### `GET /api/tasks/999` (not found)
This endpoint returns a raw `HttpResponse` with status `404` and does not use the validation adapter error formatter.
```bash
curl -i -s "$BASE_URL/api/tasks/999"
```
Representative response:
```text
HTTP/1.1 404 Not Found
Content-Type: application/json

{"detail":[{"msg":"Task not found"}]}
```

#### `POST /api/tasks` (multiple validation errors)
```bash
curl -i -s -X POST "$BASE_URL/api/tasks" \
  -H "Content-Type: application/json" \
  -d '{"title":"","priority":6}'
```
Representative response:
```text
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"detail":[{"loc":["title"],"msg":"String should have at least 1 character","type":"string_too_short"},{"loc":["priority"],"msg":"Input should be less than or equal to 5","type":"less_than_equal"}]}
```

#### `POST /api/tasks` (invalid JSON)
```bash
curl -i -s -X POST "$BASE_URL/api/tasks" \
  -H "Content-Type: application/json" \
  -d '{"title":"Deploy app","priority":2'
```
Representative response:
```text
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"detail":[{"loc":[],"msg":"Invalid JSON","type":"value_error"}]}
```

## Cleanup
```bash
az group delete --name <YOUR_RESOURCE_GROUP> --yes --no-wait
```
Representative output:
```text
{"status":"Accepted"}
```

## Sources
- [Azure Functions Python quickstart](https://learn.microsoft.com/en-us/azure/azure-functions/create-first-function-cli-python)
- [Azure Functions Core Tools publish reference](https://learn.microsoft.com/en-us/azure/azure-functions/functions-core-tools-reference#func-azure-functionapp-publish)
- [Function App settings](https://learn.microsoft.com/en-us/azure/azure-functions/functions-how-to-use-azure-function-app-settings)

## See Also
- [`azure-functions-openapi`](https://github.com/yeongseon/azure-functions-openapi)
- [`azure-functions-scaffold`](https://github.com/yeongseon/azure-functions-scaffold)
- [`azure-functions-doctor`](https://github.com/yeongseon/azure-functions-doctor)
