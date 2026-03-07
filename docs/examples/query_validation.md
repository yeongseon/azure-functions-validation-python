# Query / Path / Header Example

```python
import azure.functions as func
from pydantic import BaseModel, Field

from azure_functions_validation import validate_http


class Query(BaseModel):
    limit: int = Field(ge=1, le=100, default=10)


class Path(BaseModel):
    user_id: int = Field(ge=1)


class Headers(BaseModel):
    authorization: str


@validate_http(query=Query, path=Path, headers=Headers)
def main(
    req: func.HttpRequest,
    query: Query,
    path: Path,
    headers: Headers,
):
    return {"ok": True}
```
