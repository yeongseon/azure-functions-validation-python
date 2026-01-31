import json
import os

# Import the validation decorator
import sys
from typing import List, Optional

import azure.functions as func
from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from azure_functions_validation import validate_http


# --- Test Models ---
class UserModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    age: Optional[int] = Field(None, ge=0, le=150)

    @field_validator("name")
    def name_must_not_be_admin(cls, v):
        if v.lower() == "admin":
            raise ValueError("name cannot be admin")
        return v


class PostModel(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    tags: List[str] = Field(default_factory=list)
    is_published: bool = False


class CommentModel(BaseModel):
    post_id: int = Field(..., gt=0)
    author: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


# --- Query/Path/Header Models ---
class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(10, ge=1, le=100)
    sort_by: str = Field("created_at", pattern=r"^(created_at|updated_at|title)$")


class UpdateHeaders(BaseModel):
    x_user_id: str = Field(..., alias="X-User-ID")

    class Config:
        populate_by_name = True


# --- Response Models ---
class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    age: Optional[int] = None


class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    tags: List[str]
    is_published: bool
    created_at: str


# --- Azure Functions ---
@validate_http(body=UserModel, response_model=UserResponse)
def create_user(req: func.HttpRequest) -> func.HttpResponse:
    """Create a new user"""
    user_data = req.get_json()

    # Simulate user creation
    response_data = {
        "id": 1,
        "name": user_data["name"],
        "email": user_data["email"],
        "age": user_data.get("age"),
    }

    return func.HttpResponse(
        json.dumps(response_data), status_code=201, mimetype="application/json"
    )


@validate_http(body=PostModel, query=SearchQuery, response_model=PostResponse)
def create_post(req: func.HttpRequest) -> func.HttpResponse:
    """Create a new post with query validation"""
    post_data = req.get_json()

    # Simulate post creation
    response_data = {
        "id": 1,
        "title": post_data["title"],
        "content": post_data["content"],
        "tags": post_data["tags"],
        "is_published": post_data["is_published"],
        "created_at": "2023-01-01T00:00:00Z",
    }

    return func.HttpResponse(
        json.dumps(response_data), status_code=201, mimetype="application/json"
    )


@validate_http(path=CommentModel, response_model=dict)
def create_comment(req: func.HttpRequest) -> func.HttpResponse:
    """Create a comment with path validation"""
    # Get path parameters
    path_params = req.route_params

    # Simulate comment creation
    response_data = {
        "comment_id": 1,
        "post_id": path_params["post_id"],
        "author": path_params["author"],
        "text": path_params["text"],
        "status": "created",
    }

    return func.HttpResponse(
        json.dumps(response_data), status_code=201, mimetype="application/json"
    )


@validate_http(body=UserModel, headers=UpdateHeaders)
def update_user(
    req: func.HttpRequest, body: UserModel, headers: UpdateHeaders
) -> func.HttpResponse:
    """Update user with header validation"""
    # Headers are already validated by the decorator
    response_data = {
        "id": headers.x_user_id,
        "name": body.name,
        "email": body.email,
        "age": body.age,
        "updated": True,
    }

    return func.HttpResponse(
        json.dumps(response_data), status_code=200, mimetype="application/json"
    )


@validate_http(body=UserModel, response_model=UserResponse)
async def create_user_async(req: func.HttpRequest) -> func.HttpResponse:
    """Async version of create user"""
    import asyncio

    await asyncio.sleep(0.01)  # Simulate async work

    user_data = req.get_json()

    # Simulate user creation
    response_data = {
        "id": 1,
        "name": user_data["name"],
        "email": user_data["email"],
        "age": user_data.get("age"),
    }

    return func.HttpResponse(
        json.dumps(response_data), status_code=201, mimetype="application/json"
    )


@validate_http(body=UserModel)
def create_user_direct_response(req: func.HttpRequest) -> func.HttpResponse:
    """Function that returns HttpResponse directly"""
    user_data = req.get_json()

    return func.HttpResponse(
        json.dumps({"message": f"User {user_data['name']} created successfully", "user_id": 1}),
        status_code=201,
        mimetype="application/json",
    )


# --- Main Function App ---
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Register routes
app.route("users", methods=["POST"])(create_user)
app.route("posts", methods=["POST"])(create_post)
app.route("comments/{post_id:int}/{author}/{text}", methods=["POST"])(create_comment)
app.route("users/{id}", methods=["PUT"])(update_user)
app.route("users-async", methods=["POST"])(create_user_async)
app.route("users-direct", methods=["POST"])(create_user_direct_response)
