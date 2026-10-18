"""Fixtures-based regression tests for scripts/classify_review_evidence.py.

Fixtures are synthetic but shaped like the real provenance patterns
documented in #547 / docs/review-evidence-policy.md: #535's final-head
author-reply, #533's remapped inline-comment commit, and the
'<!-- ccr-overview-v2 -->' summary marker. No real PR data is scraped.
"""

from __future__ import annotations

from scripts.classify_review_evidence import (
    classify_inline_comment,
    classify_review,
    has_open_findings,
)

PR_AUTHOR = "yeongseon"
CURRENT_HEAD = "cccccc2"


class TestClassifyReview:
    def test_independent_review_of_current_head_is_evidence(self) -> None:
        review = {"user": {"login": "copilot-pull-request-reviewer"}, "commit_id": CURRENT_HEAD}

        result = classify_review(review, pr_author=PR_AUTHOR, current_head_sha=CURRENT_HEAD)

        assert result.is_independent is True

    def test_review_of_stale_commit_is_not_evidence(self) -> None:
        """Regression (#547): a review of an earlier commit is not evidence
        for a later head -- a push after review invalidates it."""
        review = {"user": {"login": "copilot-pull-request-reviewer"}, "commit_id": "aaaaaa1"}

        result = classify_review(review, pr_author=PR_AUTHOR, current_head_sha=CURRENT_HEAD)

        assert result.is_independent is False
        assert "stale" in result.reason

    def test_author_authored_review_is_not_independent(self) -> None:
        review = {"user": {"login": PR_AUTHOR}, "commit_id": CURRENT_HEAD}

        result = classify_review(review, pr_author=PR_AUTHOR, current_head_sha=CURRENT_HEAD)

        assert result.is_independent is False
        assert "author" in result.reason


class TestClassifyInlineComment:
    def test_number_535_final_head_author_reply_is_not_independent(self) -> None:
        """Regression (#547): #535's final-head comments were replies by the
        PR author to existing threads, not a new independent review."""
        comment = {
            "user": {"login": PR_AUTHOR},
            "original_commit_id": CURRENT_HEAD,
            "commit_id": CURRENT_HEAD,
            "in_reply_to_id": 4259275751,
        }

        result = classify_inline_comment(
            comment, pr_author=PR_AUTHOR, current_head_sha=CURRENT_HEAD
        )

        assert result.is_independent is False
        assert "reply" in result.reason

    def test_number_533_remapped_commit_id_is_not_treated_as_current(self) -> None:
        """Regression (#547): #533's inline comment has a current commit_id
        pointing at the final head, but original_commit_id (and the formal
        review) still identify the earlier reviewed commit. Must use
        original_commit_id, not the remapped commit_id."""
        comment = {
            "user": {"login": "copilot-pull-request-reviewer"},
            "original_commit_id": "aaaaaa1",
            "commit_id": CURRENT_HEAD,
            "in_reply_to_id": None,
        }

        result = classify_inline_comment(
            comment, pr_author=PR_AUTHOR, current_head_sha=CURRENT_HEAD
        )

        assert result.is_independent is False
        assert result.reviewed_commit == "aaaaaa1"

    def test_independent_comment_on_current_head_is_evidence(self) -> None:
        comment = {
            "user": {"login": "copilot-pull-request-reviewer"},
            "original_commit_id": CURRENT_HEAD,
            "commit_id": CURRENT_HEAD,
            "in_reply_to_id": None,
        }

        result = classify_inline_comment(
            comment, pr_author=PR_AUTHOR, current_head_sha=CURRENT_HEAD
        )

        assert result.is_independent is True


class TestHasOpenFindings:
    def test_number_535_three_open_findings_summary(self) -> None:
        body = "<!-- ccr-overview-v2 -->\n### \U0001f7e1 Changes recommended\n3 open findings"

        assert has_open_findings(body) is True

    def test_number_534_one_open_finding_summary(self) -> None:
        body = "<!-- ccr-overview-v2 -->\n### \U0001f7e1 Changes recommended\n1 open finding"

        assert has_open_findings(body) is True

    def test_no_findings_summary_is_not_open_findings(self) -> None:
        body = "<!-- ccr-overview-v2 -->\n### \u2705 No findings"

        assert has_open_findings(body) is False

    def test_unmarked_body_is_not_open_findings(self) -> None:
        assert has_open_findings("Looks good to me!") is False
