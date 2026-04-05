"""Tests for the workflow engine.

All browser interactions are replaced with a mock Browser so that tests
can run without a real Chrome installation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.browser import Browser, BrowserError
from src.config import StepConfig, WorkflowConfig
from src.engine import WorkflowEngine, WorkflowResult, run_workflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(steps: list[StepConfig] | None = None, **kwargs: Any) -> WorkflowConfig:
    return WorkflowConfig(
        name="test-workflow",
        start_url="https://example.com",
        steps=steps or [],
        **kwargs,
    )


def _make_mock_browser(
    current_url: str = "https://example.com/final",
    page_title: str = "Final Page",
    redirect_chain: list[str] | None = None,
) -> MagicMock:
    browser = MagicMock(spec=Browser)
    browser.current_url = current_url
    browser.page_title = page_title
    browser.redirect_chain = redirect_chain or ["https://example.com/"]
    return browser


# ---------------------------------------------------------------------------
# WorkflowResult
# ---------------------------------------------------------------------------


class TestWorkflowResult:
    def test_default_values(self):
        result = WorkflowResult(workflow_name="w")
        assert result.success is True
        assert result.error == ""
        assert result.extracted == {}
        assert result.redirect_chain == []
        assert result.elapsed_seconds == 0.0

    def test_fields_settable(self):
        result = WorkflowResult(
            workflow_name="w",
            final_url="https://x.com",
            page_title="X",
            success=False,
            error="oops",
        )
        assert result.final_url == "https://x.com"
        assert not result.success
        assert result.error == "oops"


# ---------------------------------------------------------------------------
# WorkflowEngine
# ---------------------------------------------------------------------------


class TestWorkflowEngine:
    def test_empty_steps_succeed(self):
        cfg = _make_config(steps=[])
        browser = _make_mock_browser()
        engine = WorkflowEngine(cfg, browser=browser)
        result = engine.run()
        assert result.success is True
        assert result.workflow_name == "test-workflow"

    def test_result_contains_final_url(self):
        cfg = _make_config(steps=[])
        browser = _make_mock_browser(current_url="https://example.com/end")
        engine = WorkflowEngine(cfg, browser=browser)
        result = engine.run()
        assert result.final_url == "https://example.com/end"

    def test_result_contains_page_title(self):
        cfg = _make_config(steps=[])
        browser = _make_mock_browser(page_title="Done!")
        engine = WorkflowEngine(cfg, browser=browser)
        result = engine.run()
        assert result.page_title == "Done!"

    def test_result_contains_redirect_chain(self):
        cfg = _make_config(steps=[])
        chain = ["https://start.com/", "https://end.com/"]
        browser = _make_mock_browser(redirect_chain=chain)
        engine = WorkflowEngine(cfg, browser=browser)
        result = engine.run()
        assert result.redirect_chain == chain

    def test_open_url_step_executed(self):
        step = StepConfig(action="open_url", url="https://example.com")
        cfg = _make_config(steps=[step])
        browser = _make_mock_browser()
        engine = WorkflowEngine(cfg, browser=browser)
        result = engine.run()
        browser.open.assert_called_once_with("https://example.com")
        assert result.success is True

    def test_extract_current_url_stored_in_result(self):
        step = StepConfig(action="extract_current_url", store_as="final")
        cfg = _make_config(steps=[step])
        browser = _make_mock_browser(current_url="https://example.com/page")
        engine = WorkflowEngine(cfg, browser=browser)
        result = engine.run()
        assert result.extracted.get("final") == "https://example.com/page"

    def test_browser_error_captured_in_result(self):
        step = StepConfig(action="click_element", selector_type="css", selector="#x")
        cfg = _make_config(steps=[step])
        browser = _make_mock_browser()
        browser.click.side_effect = BrowserError("Element not found")
        engine = WorkflowEngine(cfg, browser=browser)
        result = engine.run()
        assert result.success is False
        assert "Element not found" in result.error

    def test_multiple_steps_in_order(self):
        call_order: list[str] = []

        def open_side_effect(url: str) -> None:
            call_order.append(f"open:{url}")

        def wait_side_effect(s: float) -> None:
            call_order.append(f"wait:{s}")

        steps = [
            StepConfig(action="open_url", url="https://example.com"),
            StepConfig(action="wait_seconds", seconds=1.0),
        ]
        cfg = _make_config(steps=steps)
        browser = _make_mock_browser()
        browser.open.side_effect = open_side_effect
        browser.wait_seconds.side_effect = wait_side_effect

        engine = WorkflowEngine(cfg, browser=browser)
        engine.run()

        assert call_order == ["open:https://example.com", "wait:1.0"]

    def test_expected_domain_mismatch_logs_warning(self, caplog):
        import logging

        cfg = _make_config(
            steps=[],
            expected_final_domain="other.com",
        )
        browser = _make_mock_browser(current_url="https://example.com/page")
        engine = WorkflowEngine(cfg, browser=browser)
        with caplog.at_level(logging.WARNING, logger="src.engine"):
            result = engine.run()
        assert result.success is True  # mismatch is a warning, not a failure
        assert "does not match" in caplog.text

    def test_elapsed_seconds_populated(self):
        cfg = _make_config(steps=[])
        browser = _make_mock_browser()
        engine = WorkflowEngine(cfg, browser=browser)
        result = engine.run()
        assert result.elapsed_seconds >= 0.0

    def test_context_shared_across_steps(self):
        """Extraction steps should build up a shared context dict."""
        steps = [
            StepConfig(action="extract_current_url", store_as="url1"),
            StepConfig(action="extract_page_title", store_as="title1"),
        ]
        cfg = _make_config(steps=steps)
        browser = _make_mock_browser(
            current_url="https://example.com/",
            page_title="Hello",
        )
        engine = WorkflowEngine(cfg, browser=browser)
        result = engine.run()
        assert result.extracted["url1"] == "https://example.com/"
        assert result.extracted["title1"] == "Hello"


# ---------------------------------------------------------------------------
# run_workflow convenience function
# ---------------------------------------------------------------------------


class TestRunWorkflow:
    def test_convenience_function(self):
        cfg = _make_config(steps=[])
        browser = _make_mock_browser()
        result = run_workflow(cfg, browser=browser)
        assert isinstance(result, WorkflowResult)
        assert result.success is True

    def test_failed_workflow_returns_result_not_exception(self):
        step = StepConfig(action="click_element", selector_type="css", selector="#gone")
        cfg = _make_config(steps=[step])
        browser = _make_mock_browser()
        browser.click.side_effect = BrowserError("gone")
        result = run_workflow(cfg, browser=browser)
        assert result.success is False
        assert "gone" in result.error


# ---------------------------------------------------------------------------
# Retry logic (via Browser.click integration)
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Verify that the browser's retry logic works as expected.

    These tests create a real Browser mock and check that it retries clicks.
    """

    def test_click_succeeds_after_retry(self):
        """Browser.click should retry and succeed on the second attempt."""
        from unittest.mock import call, patch
        import time

        from src.browser import Browser, ElementNotFoundError

        mock_driver = MagicMock()
        mock_element = MagicMock()

        # fail once, then succeed
        mock_driver.find_element.side_effect = [
            Exception("transient"),
            mock_element,
        ]

        with patch("src.browser.webdriver.Chrome", return_value=mock_driver):
            with patch("src.browser.WebDriverWait") as mock_wait:
                # First call raises, second succeeds
                mock_wait.return_value.until.side_effect = [
                    Exception("timeout"),
                    mock_element,
                ]
                browser = Browser(headless=True)
                browser.retries = 2

                # Patch wait_for_element directly to control retry behaviour
                call_count = {"n": 0}

                def _find(by: str, value: str, *, timeout=None):
                    call_count["n"] += 1
                    if call_count["n"] == 1:
                        raise ElementNotFoundError("first attempt")
                    return mock_element

                browser.find_element = _find  # type: ignore[method-assign]
                browser.click("css", "#btn")
                assert call_count["n"] == 2

    def test_click_raises_after_exhausted_retries(self):
        from src.browser import Browser, ElementNotFoundError
        from unittest.mock import patch

        mock_driver = MagicMock()
        with patch("src.browser.webdriver.Chrome", return_value=mock_driver):
            browser = Browser(headless=True)
            browser.retries = 2

            browser.find_element = MagicMock(  # type: ignore[method-assign]
                side_effect=ElementNotFoundError("always fails")
            )
            with pytest.raises(BrowserError, match="Could not click"):
                browser.click("css", "#btn")
