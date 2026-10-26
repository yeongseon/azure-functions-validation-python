from timeit import repeat
from typing import Any

from pydantic import BaseModel, TypeAdapter


class Small(BaseModel):
    value: int


class Nested(BaseModel):
    items: list[Small]


cases: tuple[tuple[Any, Any], ...] = (
    (Small, {"value": 1}),
    (Nested, {"items": [{"value": 1}]}),
    (Small | Nested, {"value": 1}),
)
for model, data in cases:
    adapter = TypeAdapter(model)
    fresh = min(repeat(lambda: TypeAdapter(model).validate_python(data), number=10000, repeat=5))
    cached = min(repeat(lambda: adapter.validate_python(data), number=10000, repeat=5))
    print(f"{model}: fresh={fresh * 100:.3f} us cached={cached * 100:.3f} us")
