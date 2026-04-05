"""Tests for step execution handlers.

All browser interactions are mocked so no real Chrome process is needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from selenium.webdriver.common.by import By

from src.browser import Browser, BrowserError, ElementNotFoundError
from src.config import ConfigError, StepConfig
from src.steps import (
    execute_click_element,
    execute_extract_current_url,
    execute_extract_link_href,
    execute_extract_page_title,
    execute_open_url,
    execute_scroll_to_bottom,
    execute_scroll_to_element,
    execute_step,
    execute_switch_to_new_tab,
    execute_wait_for_element,
    execute_wait_seconds,
    resolve_selector,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_browser() -> MagicMock:
    """Return a MagicMock that quacks like a Browser."""
    browser = MagicMock(spec=Browser)
    browser.current_url = "https://example.com/"
    browser.page_title = "Example Domain"
    return browser


@pytest.fixture()
def context() -> dict[str, Any]:
    return {}


# ---------------------------------------------------------------------------
# resolve_selector
# ---------------------------------------------------------------------------


class TestResolveSelector:
    def test_css(self):
        step = StepConfig(action="click_element", selector_type="css", selector=".btn")
        by, value = resolve_selector(step)
        assert by == By.CSS_SELECTOR
        assert value == ".btn"

    def test_xpath(self):
        step = StepConfig(action="click_element", selector_type="xpath", selector="//div")
        by, value = resolve_selector(step)
        assert by == By.XPATH
        assert value == "//div"

    def test_id(self):
        step = StepConfig(action="click_element", selector_type="id", selector="myid")
        by, value = resolve_selector(step)
        assert by == By.ID
        assert value == "myid"

    def test_text(self):
        step = StepConfig(action="click_element", selector_type="text", selector="Click me")
        by, value = resolve_selector(step)
        assert by == By.PARTIAL_LINK_TEXT
        assert value == "Click me"


# ---------------------------------------------------------------------------
# execute_open_url
# ---------------------------------------------------------------------------


class TestExecuteOpenUrl:
    def test_opens_url(self, mock_browser, context):
        step = StepConfig(action="open_url", url="https://example.com")
        execute_open_url(step, mock_browser, context)
        mock_browser.open.assert_called_once_with("https://example.com")

    def test_empty_url_raises(self, mock_browser, context):
        step = StepConfig(action="open_url", url="")
        with pytest.raises(ConfigError, match="url"):
            execute_open_url(step, mock_browser, context)


# ---------------------------------------------------------------------------
# execute_wait_seconds
# ---------------------------------------------------------------------------


class TestExecuteWaitSeconds:
    def test_waits(self, mock_browser, context):
        step = StepConfig(action="wait_seconds", seconds=3.0)
        execute_wait_seconds(step, mock_browser, context)
        mock_browser.wait_seconds.assert_called_once_with(3.0)

    def test_negative_seconds_raises(self, mock_browser, context):
        step = StepConfig(action="wait_seconds", seconds=-1.0)
        with pytest.raises(ConfigError, match="seconds"):
            execute_wait_seconds(step, mock_browser, context)


# ---------------------------------------------------------------------------
# execute_wait_for_element
# ---------------------------------------------------------------------------


class TestExecuteWaitForElement:
    def test_calls_browser_wait(self, mock_browser, context):
        step = StepConfig(
            action="wait_for_element",
            selector_type="css",
            selector="#btn",
            timeout=10,
        )
        execute_wait_for_element(step, mock_browser, context)
        mock_browser.wait_for_element.assert_called_once_with(
            By.CSS_SELECTOR, "#btn", timeout=10
        )


# ---------------------------------------------------------------------------
# execute_click_element
# ---------------------------------------------------------------------------


class TestExecuteClickElement:
    def test_calls_browser_click(self, mock_browser, context):
        step = StepConfig(action="click_element", selector_type="id", selector="submit")
        execute_click_element(step, mock_browser, context)
        mock_browser.click.assert_called_once_with(By.ID, "submit", timeout=None)

    def test_browser_error_propagates(self, mock_browser, context):
        mock_browser.click.side_effect = BrowserError("click failed")
        step = StepConfig(action="click_element", selector_type="css", selector=".x")
        with pytest.raises(BrowserError, match="click failed"):
            execute_click_element(step, mock_browser, context)


# ---------------------------------------------------------------------------
# execute_scroll_to_bottom
# ---------------------------------------------------------------------------


class TestExecuteScrollToBottom:
    def test_calls_scroll(self, mock_browser, context):
        step = StepConfig(action="scroll_to_bottom")
        execute_scroll_to_bottom(step, mock_browser, context)
        mock_browser.scroll_to_bottom.assert_called_once()


# ---------------------------------------------------------------------------
# execute_scroll_to_element
# ---------------------------------------------------------------------------


class TestExecuteScrollToElement:
    def test_calls_scroll_to_element(self, mock_browser, context):
        step = StepConfig(
            action="scroll_to_element", selector_type="css", selector="footer"
        )
        execute_scroll_to_element(step, mock_browser, context)
        mock_browser.scroll_to_element.assert_called_once_with(By.CSS_SELECTOR, "footer")


# ---------------------------------------------------------------------------
# execute_switch_to_new_tab
# ---------------------------------------------------------------------------


class TestExecuteSwitchToNewTab:
    def test_calls_switch(self, mock_browser, context):
        step = StepConfig(action="switch_to_new_tab", timeout=5)
        execute_switch_to_new_tab(step, mock_browser, context)
        mock_browser.switch_to_new_tab.assert_called_once_with(timeout=5)


# ---------------------------------------------------------------------------
# execute_extract_current_url
# ---------------------------------------------------------------------------


class TestExecuteExtractCurrentUrl:
    def test_stores_url_with_default_key(self, mock_browser, context):
        mock_browser.current_url = "https://result.example.com/"
        step = StepConfig(action="extract_current_url")
        execute_extract_current_url(step, mock_browser, context)
        assert context["current_url"] == "https://result.example.com/"

    def test_stores_url_with_custom_key(self, mock_browser, context):
        mock_browser.current_url = "https://result.example.com/"
        step = StepConfig(action="extract_current_url", store_as="my_url")
        execute_extract_current_url(step, mock_browser, context)
        assert context["my_url"] == "https://result.example.com/"


# ---------------------------------------------------------------------------
# execute_extract_link_href
# ---------------------------------------------------------------------------


class TestExecuteExtractLinkHref:
    def test_stores_href_with_default_key(self, mock_browser, context):
        mock_browser.extract_link_href.return_value = "https://dest.example.com/"
        step = StepConfig(
            action="extract_link_href", selector_type="css", selector="a#link"
        )
        execute_extract_link_href(step, mock_browser, context)
        assert context["link_href"] == "https://dest.example.com/"

    def test_stores_href_with_custom_key(self, mock_browser, context):
        mock_browser.extract_link_href.return_value = "https://dest.example.com/"
        step = StepConfig(
            action="extract_link_href",
            selector_type="css",
            selector="a#link",
            store_as="dest",
        )
        execute_extract_link_href(step, mock_browser, context)
        assert context["dest"] == "https://dest.example.com/"


# ---------------------------------------------------------------------------
# execute_extract_page_title
# ---------------------------------------------------------------------------


class TestExecuteExtractPageTitle:
    def test_stores_title_with_default_key(self, mock_browser, context):
        mock_browser.page_title = "My Page"
        step = StepConfig(action="extract_page_title")
        execute_extract_page_title(step, mock_browser, context)
        assert context["page_title"] == "My Page"

    def test_stores_title_with_custom_key(self, mock_browser, context):
        mock_browser.page_title = "My Page"
        step = StepConfig(action="extract_page_title", store_as="title")
        execute_extract_page_title(step, mock_browser, context)
        assert context["title"] == "My Page"


# ---------------------------------------------------------------------------
# execute_step dispatcher
# ---------------------------------------------------------------------------


class TestExecuteStep:
    def test_dispatches_open_url(self, mock_browser, context):
        step = StepConfig(action="open_url", url="https://example.com")
        execute_step(step, mock_browser, context)
        mock_browser.open.assert_called_once()

    def test_dispatches_wait_seconds(self, mock_browser, context):
        step = StepConfig(action="wait_seconds", seconds=1.0)
        execute_step(step, mock_browser, context)
        mock_browser.wait_seconds.assert_called_once_with(1.0)

    def test_dispatches_scroll_to_bottom(self, mock_browser, context):
        step = StepConfig(action="scroll_to_bottom")
        execute_step(step, mock_browser, context)
        mock_browser.scroll_to_bottom.assert_called_once()

    def test_step_label_used_in_logging(self, mock_browser, context, caplog):
        import logging

        step = StepConfig(action="scroll_to_bottom", label="my fancy label")
        with caplog.at_level(logging.INFO, logger="src.steps"):
            execute_step(step, mock_browser, context)
        assert "my fancy label" in caplog.text
