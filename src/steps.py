"""Step execution logic.

Each public function in this module corresponds to a workflow *action* name
and carries out the described operation against a :class:`~src.browser.Browser`
instance, storing results into the shared *context* dict.
"""

from __future__ import annotations

import logging
from typing import Any

from selenium.webdriver.common.by import By

from src.browser import Browser, BrowserError
from src.config import ConfigError, StepConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Selector helpers
# ---------------------------------------------------------------------------

_SELECTOR_MAP: dict[str, str] = {
    "css": By.CSS_SELECTOR,
    "xpath": By.XPATH,
    "id": By.ID,
    "text": By.PARTIAL_LINK_TEXT,
}


def resolve_selector(step: StepConfig) -> tuple[str, str]:
    """Return the ``(by, value)`` pair for a step's selector.

    Args:
        step: The step whose selector should be resolved.

    Returns:
        A ``(by, value)`` tuple compatible with Selenium's ``find_element``.

    Raises:
        ConfigError: If the selector_type is unknown.
    """
    by = _SELECTOR_MAP.get(step.selector_type)
    if by is None:
        raise ConfigError(
            f"Unknown selector_type {step.selector_type!r}. "
            f"Valid types: {sorted(_SELECTOR_MAP)}"
        )
    return by, step.selector


# ---------------------------------------------------------------------------
# Individual step handlers
# ---------------------------------------------------------------------------


def execute_open_url(step: StepConfig, browser: Browser, context: dict[str, Any]) -> None:
    """Navigate the browser to the URL specified in *step*.

    Args:
        step: Step configuration containing ``url``.
        browser: Active browser session.
        context: Shared mutable context dict (unused but kept for signature consistency).
    """
    if not step.url:
        raise ConfigError("'open_url' step requires a non-empty 'url' field.")
    browser.open(step.url)


def execute_wait_seconds(
    step: StepConfig, browser: Browser, context: dict[str, Any]
) -> None:
    """Pause for the number of seconds specified in *step*.

    Args:
        step: Step configuration containing ``seconds``.
        browser: Active browser session.
        context: Shared mutable context dict (unused).
    """
    if step.seconds < 0:
        raise ConfigError("'wait_seconds' step requires 'seconds' >= 0.")
    browser.wait_seconds(step.seconds)


def execute_wait_for_element(
    step: StepConfig, browser: Browser, context: dict[str, Any]
) -> None:
    """Wait until the element identified by *step*'s selector is visible.

    Args:
        step: Step configuration with selector fields.
        browser: Active browser session.
        context: Shared mutable context dict (unused).
    """
    by, value = resolve_selector(step)
    browser.wait_for_element(by, value, timeout=step.timeout)


def execute_click_element(
    step: StepConfig, browser: Browser, context: dict[str, Any]
) -> None:
    """Click the element identified by *step*'s selector.

    Args:
        step: Step configuration with selector fields.
        browser: Active browser session.
        context: Shared mutable context dict (unused).
    """
    by, value = resolve_selector(step)
    browser.click(by, value, timeout=step.timeout)


def execute_scroll_to_bottom(
    step: StepConfig, browser: Browser, context: dict[str, Any]
) -> None:
    """Scroll the page to the bottom.

    Args:
        step: Step configuration (no extra fields required).
        browser: Active browser session.
        context: Shared mutable context dict (unused).
    """
    browser.scroll_to_bottom()


def execute_scroll_to_element(
    step: StepConfig, browser: Browser, context: dict[str, Any]
) -> None:
    """Scroll the page until the target element is in view.

    Args:
        step: Step configuration with selector fields.
        browser: Active browser session.
        context: Shared mutable context dict (unused).
    """
    by, value = resolve_selector(step)
    browser.scroll_to_element(by, value)


def execute_switch_to_new_tab(
    step: StepConfig, browser: Browser, context: dict[str, Any]
) -> None:
    """Switch driver focus to a newly opened browser tab.

    Args:
        step: Step configuration with optional ``timeout``.
        browser: Active browser session.
        context: Shared mutable context dict (unused).
    """
    browser.switch_to_new_tab(timeout=step.timeout)


def execute_extract_current_url(
    step: StepConfig, browser: Browser, context: dict[str, Any]
) -> None:
    """Store the browser's current URL in *context*.

    Args:
        step: Step configuration with optional ``store_as``.
        browser: Active browser session.
        context: Shared mutable context dict; the URL is stored under
            ``step.store_as`` or the key ``"current_url"``.
    """
    url = browser.current_url
    key = step.store_as or "current_url"
    context[key] = url
    logger.info("extract_current_url → %s = %s", key, url)


def execute_extract_link_href(
    step: StepConfig, browser: Browser, context: dict[str, Any]
) -> None:
    """Extract the href of a link element and store it in *context*.

    Args:
        step: Step configuration with selector fields and optional ``store_as``.
        browser: Active browser session.
        context: Shared mutable context dict; the href is stored under
            ``step.store_as`` or ``"link_href"``.
    """
    by, value = resolve_selector(step)
    href = browser.extract_link_href(by, value)
    key = step.store_as or "link_href"
    context[key] = href
    logger.info("extract_link_href → %s = %s", key, href)


def execute_extract_page_title(
    step: StepConfig, browser: Browser, context: dict[str, Any]
) -> None:
    """Store the current page title in *context*.

    Args:
        step: Step configuration with optional ``store_as``.
        browser: Active browser session.
        context: Shared mutable context dict; the title is stored under
            ``step.store_as`` or ``"page_title"``.
    """
    title = browser.page_title
    key = step.store_as or "page_title"
    context[key] = title
    logger.info("extract_page_title → %s = %s", key, title)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

STEP_HANDLERS: dict[
    str,
    Any,
] = {
    "open_url": execute_open_url,
    "wait_seconds": execute_wait_seconds,
    "wait_for_element": execute_wait_for_element,
    "click_element": execute_click_element,
    "scroll_to_bottom": execute_scroll_to_bottom,
    "scroll_to_element": execute_scroll_to_element,
    "switch_to_new_tab": execute_switch_to_new_tab,
    "extract_current_url": execute_extract_current_url,
    "extract_link_href": execute_extract_link_href,
    "extract_page_title": execute_extract_page_title,
}


def execute_step(
    step: StepConfig, browser: Browser, context: dict[str, Any]
) -> None:
    """Dispatch a single workflow step to its handler.

    Args:
        step: The step to execute.
        browser: Active browser session.
        context: Shared mutable context dict passed to the handler.

    Raises:
        ConfigError: If no handler exists for the step's action.
        BrowserError: Propagated from the underlying browser calls.
    """
    handler = STEP_HANDLERS.get(step.action)
    if handler is None:
        raise ConfigError(f"No handler for action {step.action!r}")
    label = step.label or step.action
    logger.info("[step] %s", label)
    handler(step, browser, context)
