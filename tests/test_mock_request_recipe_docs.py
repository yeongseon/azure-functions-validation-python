"""Keep the MockHttpRequest recipe page in sync with the recipe file (#634)."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_RECIPE = _ROOT / "tests" / "test_mock_request_recipe.py"
_PAGE = _ROOT / "docs" / "examples" / "mock_request_testing.md"


def test_docs_page_embeds_the_recipe_verbatim() -> None:
    recipe = _RECIPE.read_text(encoding="utf-8")
    assert f"```python\n{recipe}```" in _PAGE.read_text(encoding="utf-8")


def test_docs_page_states_the_documented_helper_behaviour() -> None:
    page = _PAGE.read_text(encoding="utf-8")
    for claim in ("mutually exclusive", "`ValueError`", "Content-Type: application/json"):
        assert claim in page
