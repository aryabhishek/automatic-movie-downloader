"""Workflow execution engine.

This module ties together :class:`~src.browser.Browser`,
:class:`~src.config.WorkflowConfig`, and the step handlers in
:mod:`src.steps` to run a full end-to-end redirect navigation workflow.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from src.browser import Browser, BrowserError, managed_browser
from src.config import WorkflowConfig
from src.steps import execute_step

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class WorkflowResult:
    """Holds the outcome of a completed workflow run.

    Attributes:
        workflow_name: Name taken from the config.
        final_url: The URL the browser was on when the workflow finished.
        page_title: Browser page title at the end.
        redirect_chain: All URLs navigated during the session.
        extracted: Key/value pairs stored by extraction steps.
        elapsed_seconds: Total wall-clock time in seconds.
        success: *True* if the workflow completed without error.
        error: Human-readable error message when ``success`` is *False*.
    """

    workflow_name: str
    final_url: str = ""
    page_title: str = ""
    redirect_chain: list[str] = field(default_factory=list)
    extracted: dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    success: bool = True
    error: str = ""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class WorkflowEngine:
    """Executes a :class:`~src.config.WorkflowConfig` against a browser.

    Parameters
    ----------
    config:
        The workflow to run.
    browser:
        An already-started :class:`~src.browser.Browser` instance.  When
        *None*, :meth:`run` will start and manage its own browser.
    """

    def __init__(
        self,
        config: WorkflowConfig,
        browser: Browser | None = None,
    ) -> None:
        self.config = config
        self._browser = browser

    def run(self) -> WorkflowResult:
        """Execute the workflow and return a :class:`WorkflowResult`.

        If no browser was injected at construction time a new one is created
        (headless by default, controlled by ``config.headless``).

        Returns:
            A fully-populated :class:`WorkflowResult`.
        """
        result = WorkflowResult(workflow_name=self.config.name)
        start = time.monotonic()

        if self._browser is not None:
            result = self._execute(self._browser, result)
        else:
            with managed_browser(
                headless=self.config.headless,
                timeout=self.config.timeout,
                retries=self.config.retries,
            ) as browser:
                result = self._execute(browser, result)

        result.elapsed_seconds = time.monotonic() - start
        return result

    def _execute(self, browser: Browser, result: WorkflowResult) -> WorkflowResult:
        """Run all steps against *browser* and populate *result*.

        Args:
            browser: Active browser session.
            result: Result object to populate in-place.

        Returns:
            The same *result* object, fully populated.
        """
        context: dict[str, Any] = {}

        try:
            for idx, step in enumerate(self.config.steps, start=1):
                label = step.label or step.action
                logger.info("--- Step %d/%d: %s ---", idx, len(self.config.steps), label)
                execute_step(step, browser, context)

            result.final_url = browser.current_url
            result.page_title = browser.page_title
            result.redirect_chain = browser.redirect_chain
            result.extracted = dict(context)
            result.success = True

            # Optionally verify the final domain matches expectation
            expected = self.config.expected_final_domain
            if expected:
                actual_domain = urlparse(result.final_url).netloc
                if expected not in actual_domain:
                    logger.warning(
                        "Final domain %r does not match expected %r",
                        actual_domain,
                        expected,
                    )

        except (BrowserError, Exception) as exc:  # noqa: BLE001
            # Catch-all is intentional: step handlers can raise from Selenium
            # internals, configuration errors, or unexpected JavaScript state.
            # We surface every failure as a structured result instead of letting
            # it propagate unhandled to the caller.
            result.success = False
            result.error = str(exc)
            result.final_url = browser.current_url
            result.page_title = browser.page_title
            result.redirect_chain = browser.redirect_chain
            result.extracted = dict(context)
            logger.error("Workflow failed at step: %s", exc)

        return result


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def run_workflow(
    config: WorkflowConfig,
    browser: Browser | None = None,
) -> WorkflowResult:
    """Create a :class:`WorkflowEngine` and immediately run the workflow.

    Args:
        config: The workflow configuration to execute.
        browser: Optional pre-created browser (useful for testing).

    Returns:
        A :class:`WorkflowResult` describing what happened.
    """
    engine = WorkflowEngine(config, browser=browser)
    return engine.run()
