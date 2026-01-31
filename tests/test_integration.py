import json
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_test_app"))

import azure.functions as func
from function_app import (
    create_comment,
    create_post,
    create_user,
    create_user_async,
    create_user_direct_response,
    update_user,
)


class MockHttpRequest:
    """Mock HttpRequest class for testing"""

    def __init__(
        self, method="GET", url=None, body=None, headers=None, params=None, route_params=None
    ):
        self._method = method
        self._url = url or "/"
        self._body = body or b""
        self._headers = headers or {}
        self._params = params or {}
        self._route_params = route_params or {}

    @property
    def method(self):
        return self._method

    @property
    def url(self):
        return self._url

    @property
    def headers(self):
        return self._headers

    @property
    def params(self):
        return self._params

    @property
    def route_params(self):
        return self._route_params

    def get_body(self):
        return self._body

    def get_json(self):
        """Parse JSON body and return as dict"""
        if not self._body:
            return None
        try:
            return json.loads(self._body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None


class TestIntegration:
    """Integration tests with actual Azure Function calls"""

    def test_create_user_success(self):
        """Test successful user creation"""
        request = func.HttpRequest(
            method="POST",
            url="/api/users",
            body=json.dumps({"name": "John Doe", "email": "john@example.com", "age": 30}).encode(
                "utf-8"
            ),
            headers={"Content-Type": "application/json"},
        )

        response = create_user(request)

        assert response.status_code == 201
        response_data = json.loads(response.get_body())
        assert response_data["name"] == "John Doe"
        assert response_data["email"] == "john@example.com"
        assert response_data["age"] == 30
        assert "id" in response_data

    def test_create_user_validation_error(self):
        """Test user creation with invalid data"""
        request = func.HttpRequest(
            method="POST",
            url="/api/users",
            body=json.dumps(
                {
                    "name": "",  # Invalid: empty name
                    "email": "invalid-email",  # Invalid: not an email
                    "age": -5,  # Invalid: negative age
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        response = create_user(request)

        assert response.status_code == 422
        response_data = json.loads(response.get_body())
        assert "detail" in response_data
        assert len(response_data["detail"]) == 3  # 3 validation errors

    def test_create_user_empty_body(self):
        """Test user creation with empty body"""
        request = func.HttpRequest(
            method="POST", url="/api/users", body=b"", headers={"Content-Type": "application/json"}
        )

        response = create_user(request)

        assert response.status_code == 422
        response_data = json.loads(response.get_body())
        assert "detail" in response_data

    def test_create_post_success(self):
        """Test successful post creation"""
        request = MockHttpRequest(
            method="POST",
            url="/api/posts?query=test&limit=5&sort_by=title",
            body=json.dumps(
                {
                    "title": "Test Post",
                    "content": "This is test content",
                    "tags": ["test", "post"],
                    "is_published": True,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            params={"query": "test", "limit": "5", "sort_by": "title"},
        )

        response = create_post(request)

        assert response.status_code == 201
        response_data = json.loads(response.get_body())
        assert response_data["title"] == "Test Post"
        assert response_data["content"] == "This is test content"
        assert response_data["tags"] == ["test", "post"]
        assert response_data["is_published"] is True

    def test_create_post_invalid_query(self):
        """Test post creation with invalid query parameters"""
        request = MockHttpRequest(
            method="POST",
            url="/api/posts?query=&limit=200&sort_by=invalid",
            body=json.dumps(
                {
                    "title": "Test Post",
                    "content": "This is test content",
                    "tags": [],
                    "is_published": False,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            params={"query": "", "limit": "200", "sort_by": "invalid"},
        )

        response = create_post(request)

        assert response.status_code == 422
        response_data = json.loads(response.get_body())
        assert "detail" in response_data
        assert len(response_data["detail"]) == 3  # 3 query validation errors

    def test_create_comment_success(self):
        """Test successful comment creation"""
        request = MockHttpRequest(
            method="POST",
            url="/api/comments/123/John/This%20is%20a%20comment",
            body=b"",
            headers={},
            route_params={"post_id": "123", "author": "John", "text": "This is a comment"},
        )

        response = create_comment(request)

        assert response.status_code == 201
        response_data = json.loads(response.get_body())
        assert response_data["post_id"] == "123"
        assert response_data["author"] == "John"
        assert response_data["text"] == "This is a comment"
        assert response_data["status"] == "created"

    def test_create_comment_invalid_path(self):
        """Test comment creation with invalid path parameters"""
        request = MockHttpRequest(
            method="POST",
            url="/api/comments/0//",
            body=b"",
            headers={},
            route_params={
                "post_id": "0",  # Invalid: must be > 0
                "author": "",  # Invalid: empty
                "text": "",  # Invalid: empty
            },
        )

        response = create_comment(request)

        assert response.status_code == 422
        response_data = json.loads(response.get_body())
        assert "detail" in response_data
        assert len(response_data["detail"]) == 3  # 3 path validation errors

    def test_update_user_success(self):
        """Test successful user update"""
        request = MockHttpRequest(
            method="PUT",
            url="/api/users/123",
            body=json.dumps({"name": "Jane Doe", "email": "jane@example.com", "age": 25}).encode(
                "utf-8"
            ),
            headers={"Content-Type": "application/json", "X-User-ID": "123"},
        )

        response = update_user(request)

        assert response.status_code == 200
        response_data = json.loads(response.get_body())
        assert response_data["id"] == "123"
        assert response_data["name"] == "Jane Doe"
        assert response_data["email"] == "jane@example.com"
        assert response_data["updated"] is True

    def test_update_user_missing_header(self):
        """Test user update with missing required header"""
        request = MockHttpRequest(
            method="PUT",
            url="/api/users/123",
            body=json.dumps({"name": "Jane Doe", "email": "jane@example.com"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},  # Missing X-User-ID
        )

        response = update_user(request)

        assert response.status_code == 422
        response_data = json.loads(response.get_body())
        assert "detail" in response_data
        # Should have validation error for missing X-User-ID header
        header_error = any(
            "X-User-ID" in str(error) or "Field required" in str(error)
            for error in response_data["detail"]
        )
        assert header_error

    def test_create_user_async_success(self):
        """Test successful async user creation"""

        request = func.HttpRequest(
            method="POST",
            url="/api/users-async",
            body=json.dumps({"name": "Async User", "email": "async@example.com", "age": 35}).encode(
                "utf-8"
            ),
            headers={"Content-Type": "application/json"},
        )

        # Call the async function directly (it's already wrapped by the decorator)
        response = create_user_async(request)

        assert response.status_code == 201
        response_data = json.loads(response.get_body())
        assert response_data["name"] == "Async User"
        assert response_data["email"] == "async@example.com"
        assert response_data["age"] == 35

    def test_create_user_direct_response_success(self):
        """Test function that returns HttpResponse directly"""
        request = func.HttpRequest(
            method="POST",
            url="/api/users-direct",
            body=json.dumps(
                {"name": "Direct User", "email": "direct@example.com", "age": 40}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        response = create_user_direct_response(request)

        assert response.status_code == 201
        response_data = json.loads(response.get_body())
        assert "message" in response_data
        assert "Direct User" in response_data["message"]
        assert response_data["user_id"] == 1

    def test_admin_name_validation(self):
        """Test that 'admin' name is rejected"""
        request = func.HttpRequest(
            method="POST",
            url="/api/users",
            body=json.dumps(
                {
                    "name": "admin",  # Invalid: 'admin' is not allowed
                    "email": "admin@example.com",
                    "age": 30,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        response = create_user(request)

        assert response.status_code == 422
        response_data = json.loads(response.get_body())
        assert "detail" in response_data
        # Check that one of the validation errors is about the name
        name_error = any(
            "name cannot be admin" in str(error).lower() for error in response_data["detail"]
        )
        assert name_error

    def test_malformed_json(self):
        """Test handling of malformed JSON"""
        request = func.HttpRequest(
            method="POST",
            url="/api/users",
            body=(
                b'{"name": "John", "email": "john@example.com", "age": 30'  # Missing closing brace
            ),
            headers={"Content-Type": "application/json"},
        )

        response = create_user(request)

        assert response.status_code == 400
        response_data = json.loads(response.get_body())
        assert "detail" in response_data
        # Should be a JSON parsing error
        detail = response_data["detail"]
        if isinstance(detail, list):
            detail_str = str(detail[0]) if detail else str(detail)
        else:
            detail_str = str(detail)
        assert "json" in detail_str.lower() or "parse" in detail_str.lower()

    def test_wrong_content_type(self):
        """Test handling of wrong content type"""
        request = func.HttpRequest(
            method="POST",
            url="/api/users",
            body=b"name=John&email=john@example.com&age=30",  # Form data, not JSON
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        response = create_user(request)

        # This should either fail JSON parsing or be handled as empty body
        assert response.status_code in [400, 422]
        response_data = json.loads(response.get_body())
        assert "detail" in response_data

    def test_large_payload(self):
        """Test handling of large payload"""
        large_name = "x" * 200  # Exceeds max_length of 100

        request = func.HttpRequest(
            method="POST",
            url="/api/users",
            body=json.dumps({"name": large_name, "email": "john@example.com", "age": 30}).encode(
                "utf-8"
            ),
            headers={"Content-Type": "application/json"},
        )

        response = create_user(request)

        assert response.status_code == 422
        response_data = json.loads(response.get_body())
        assert "detail" in response_data
        # Should have validation error for name length
        name_error = any(
            "name" in str(error).lower()
            and ("length" in str(error).lower() or "characters" in str(error).lower())
            for error in response_data["detail"]
        )
        assert name_error
