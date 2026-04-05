"""Browser wrapper module.

Provides a high-level, context-manager-friendly wrapper around a headless
(or headed) Chrome/Chromium browser driven by Selenium 4.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchWindowException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT: int = 30
DEFAULT_RETRIES: int = 3
RETRY_DELAY: float = 1.0


class BrowserError(Exception):
    """Raised when the browser encounters an unrecoverable error."""


class ElementNotFoundError(BrowserError):
    """Raised when a required element cannot be located within the timeout."""


def _build_options(headless: bool, extra_args: list[str] | None = None) -> Options:
    """Construct ChromeOptions for the session.

    Args:
        headless: Run in headless mode when *True*.
        extra_args: Additional Chrome command-line arguments.

    Returns:
        Configured :class:`Options` object.
    """
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-popup-blocking")
    for arg in extra_args or []:
        opts.add_argument(arg)
    return opts


class Browser:
    """Thin wrapper around a Selenium WebDriver instance.

    Parameters
    ----------
    headless:
        Use headless Chrome when *True* (default).
    timeout:
        Default explicit-wait timeout in seconds.
    retries:
        Number of retry attempts for transient failures.
    chrome_driver_path:
        Optional path to a specific chromedriver binary; *None* lets Selenium
        locate one automatically.
    extra_args:
        Additional Chrome command-line flags.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        chrome_driver_path: str | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self._redirect_chain: list[str] = []

        opts = _build_options(headless, extra_args)
        service = Service(chrome_driver_path) if chrome_driver_path else Service()
        logger.debug("Starting Chrome (headless=%s)", headless)
        self.driver: WebDriver = webdriver.Chrome(service=service, options=opts)
        logger.info("Browser session started")

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def open(self, url: str) -> None:
        """Navigate to *url* and record it in the redirect chain.

        Args:
            url: The URL to load.
        """
        logger.info("open_url → %s", url)
        self._redirect_chain.append(url)
        self.driver.get(url)

    @property
    def current_url(self) -> str:
        """Return the browser's current URL."""
        return self.driver.current_url

    @property
    def page_title(self) -> str:
        """Return the current page title."""
        return self.driver.title

    @property
    def redirect_chain(self) -> list[str]:
        """Return a copy of the recorded redirect chain."""
        return list(self._redirect_chain)

    # ------------------------------------------------------------------
    # Waiting helpers
    # ------------------------------------------------------------------

    def wait_for_element(
        self,
        by: str,
        value: str,
        *,
        timeout: int | None = None,
    ) -> WebElement:
        """Wait until an element is visible and return it.

        Args:
            by: A Selenium ``By`` string constant such as ``By.CSS_SELECTOR``,
                ``By.XPATH``, ``By.ID``, or ``By.PARTIAL_LINK_TEXT``.
            value: The selector value.
            timeout: Override the instance-level timeout.

        Returns:
            The located :class:`WebElement`.

        Raises:
            ElementNotFoundError: If the element is not found within the timeout.
        """
        t = timeout if timeout is not None else self.timeout
        try:
            wait = WebDriverWait(self.driver, t)
            element = wait.until(EC.visibility_of_element_located((by, value)))
            return element
        except TimeoutException as exc:
            raise ElementNotFoundError(
                f"Element not found after {t}s: by={by!r} value={value!r}"
            ) from exc

    def wait_seconds(self, seconds: float) -> None:
        """Pause execution for *seconds* seconds.

        Args:
            seconds: Number of seconds to wait.
        """
        logger.info("wait_seconds → %.1fs", seconds)
        time.sleep(seconds)

    # ------------------------------------------------------------------
    # Element interaction
    # ------------------------------------------------------------------

    def find_element(
        self, by: str, value: str, *, timeout: int | None = None
    ) -> WebElement:
        """Locate an element with an explicit wait.

        Args:
            by: Selenium ``By`` constant.
            value: Selector value.
            timeout: Optional timeout override.

        Returns:
            The found :class:`WebElement`.
        """
        return self.wait_for_element(by, value, timeout=timeout)

    def click(self, by: str, value: str, *, timeout: int | None = None) -> None:
        """Wait for an element then click it, with automatic retries.

        Args:
            by: Selenium ``By`` constant.
            value: Selector value.
            timeout: Optional timeout override.

        Raises:
            BrowserError: If the element cannot be clicked after all retries.
        """
        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                elem = self.find_element(by, value, timeout=timeout)
                elem.click()
                logger.info("click → by=%s value=%s (attempt %d)", by, value, attempt)
                return
            except (ElementNotFoundError, WebDriverException) as exc:
                last_exc = exc
                logger.warning(
                    "click attempt %d/%d failed: %s", attempt, self.retries, exc
                )
                if attempt < self.retries:
                    time.sleep(RETRY_DELAY)
        raise BrowserError(
            f"Could not click element after {self.retries} attempts: {last_exc}"
        )

    # ------------------------------------------------------------------
    # Scroll helpers
    # ------------------------------------------------------------------

    def scroll_to_bottom(self) -> None:
        """Scroll the page to the very bottom."""
        logger.info("scroll_to_bottom")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    def scroll_to_element(self, by: str, value: str) -> None:
        """Scroll until an element is in the viewport.

        Args:
            by: Selenium ``By`` constant.
            value: Selector value.
        """
        elem = self.find_element(by, value)
        self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
        logger.info("scroll_to_element → by=%s value=%s", by, value)

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def switch_to_new_tab(self, *, timeout: int | None = None) -> None:
        """Wait for a new tab to open and switch to it.

        Args:
            timeout: Seconds to wait for the new tab.

        Raises:
            BrowserError: If no new tab appears within the timeout.
        """
        t = timeout if timeout is not None else self.timeout
        original_handles = set(self.driver.window_handles)
        deadline = time.monotonic() + t
        while time.monotonic() < deadline:
            new_handles = set(self.driver.window_handles) - original_handles
            if new_handles:
                new_handle = next(iter(new_handles))
                self.driver.switch_to.window(new_handle)
                logger.info("switch_to_new_tab → handle %s", new_handle)
                self._redirect_chain.append(self.driver.current_url)
                return
            time.sleep(0.5)
        raise BrowserError(f"No new tab appeared within {t}s")

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def extract_link_href(self, by: str, value: str) -> str:
        """Return the *href* attribute of a link element.

        Args:
            by: Selenium ``By`` constant.
            value: Selector value.

        Returns:
            The ``href`` value as a string.
        """
        elem = self.find_element(by, value)
        href = elem.get_attribute("href") or ""
        logger.info("extract_link_href → %s", href)
        return href

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def quit(self) -> None:
        """Close all windows and terminate the browser process."""
        try:
            self.driver.quit()
            logger.info("Browser session closed")
        except (WebDriverException, NoSuchWindowException) as exc:
            logger.warning("Error while quitting browser: %s", exc)

    def __enter__(self) -> "Browser":
        return self

    def __exit__(self, *_: object) -> None:
        self.quit()


@contextmanager
def managed_browser(**kwargs: object) -> Generator[Browser, None, None]:
    """Context manager that creates a :class:`Browser` and guarantees cleanup.

    Keyword arguments are forwarded to :class:`Browser`.

    Yields:
        A ready-to-use :class:`Browser` instance.
    """
    browser = Browser(**kwargs)  # type: ignore[arg-type]
    try:
        yield browser
    finally:
        browser.quit()
