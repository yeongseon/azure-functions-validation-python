# CRUD API Example

## Overview

This example implements a task management REST API that demonstrates the full
range of `azure-functions-validation` features in a single function app.

Use this as a reference when building a realistic multi-endpoint API that
combines body, query, path, and response validation.

## What It Shows

- **Body validation** with field constraints (`min_length`, `ge`, `le`)
- **Query parameter filtering** on list endpoints
- **Path parameter validation** with `task_id: int = Field(ge=1)`
- **List response model** using `response_model=list[TaskResponse]`
- **`request_model` shorthand** as a convenient alias for `body`
- **Combined body + path** validation in a single handler
- **`HttpResponse` bypass** for endpoints that return non-JSON responses (204)

## Endpoints

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/api/tasks` | List tasks with optional `done` / `priority` filters |
| `GET` | `/api/tasks/{task_id}` | Get a single task by id |
| `POST` | `/api/tasks` | Create a task (`request_model` shorthand) |
| `PATCH` | `/api/tasks/{task_id}` | Partial update (body + path combined) |
| `DELETE` | `/api/tasks/{task_id}` | Delete a task (HttpResponse bypass, 204) |

## Models

```python
from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    priority: int = Field(ge=1, le=5, default=3)


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    priority: int | None = Field(default=None, ge=1, le=5)
    done: bool | None = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str
    priority: int
    done: bool


class TaskPath(BaseModel):
    task_id: int = Field(ge=1)


class TaskListQuery(BaseModel):
    done: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
```

## Key Patterns

### List endpoint with query filters

```python
@validate_http(query=TaskListQuery, response_model=list[TaskResponse])
def list_tasks(req: func.HttpRequest, query: TaskListQuery) -> list[dict]:
    results = list(_TASKS.values())
    if query.done is not None:
        results = [t for t in results if t["done"] == query.done]
    if query.priority is not None:
        results = [t for t in results if t["priority"] == query.priority]
    return results
```

The `response_model=list[TaskResponse]` validates that every item in the
returned list conforms to `TaskResponse`.

### `request_model` shorthand

```python
@validate_http(request_model=TaskCreateRequest, response_model=TaskResponse)
def create_task(req: func.HttpRequest, req_model: TaskCreateRequest) -> TaskResponse:
    ...
```

`request_model=TaskCreateRequest` is equivalent to `body=TaskCreateRequest`.
The validated object is injected as the `req_model` parameter.

### Combined body + path validation

```python
@validate_http(body=TaskUpdateRequest, path=TaskPath, response_model=TaskResponse)
def update_task(
    req: func.HttpRequest,
    body: TaskUpdateRequest,
    path: TaskPath,
) -> dict | func.HttpResponse:
    task = _TASKS.get(path.task_id)
    if task is None:
        return func.HttpResponse(
            body='{"detail": [{"msg": "Task not found"}]}',
            status_code=404,
            headers={"Content-Type": "application/json"},
        )
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        task[key] = value
    return task
```

When the handler returns an `HttpResponse` directly, response model validation
is bypassed — useful for 404 or other non-standard responses.

### HttpResponse bypass (DELETE → 204)

```python
@validate_http(path=TaskPath)
def delete_task(req: func.HttpRequest, path: TaskPath) -> func.HttpResponse:
    _TASKS.pop(path.task_id, None)
    return func.HttpResponse(status_code=204)
```

No `response_model` is needed when the handler always returns an
`HttpResponse`. The path parameter is still validated.

## Expected Responses

List all tasks (`GET /api/tasks`):

```json
[
  {"id": 1, "title": "Write docs", "description": "Add examples", "priority": 2, "done": false},
  {"id": 2, "title": "Fix bug #42", "description": "", "priority": 5, "done": true},
  {"id": 3, "title": "Add tests", "description": "Cover edge cases", "priority": 3, "done": false}
]
```

Filter by status (`GET /api/tasks?done=true`):

```json
[
  {"id": 2, "title": "Fix bug #42", "description": "", "priority": 5, "done": true}
]
```

Invalid path parameter (`GET /api/tasks/0`):

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["path", "task_id"],
      "msg": "Input should be greater than or equal to 1"
    }
  ]
}
```

## Smoke Coverage

This example is smoke-tested in `tests/test_examples.py` with 21 test cases
covering all endpoints, query filters, validation errors, 404 responses, and
the 204 delete path.
