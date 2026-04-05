"""Configuration model and parsing for workflow definitions.

Workflows are described in YAML or JSON files. This module provides
dataclass-based models and validation for those definitions.

Example YAML layout::

    name: my-workflow
    start_url: https://example.com
    steps:
      - action: open_url
        url: https://example.com
      - action: wait_seconds
        seconds: 3
    expected_final_domain: example.com
    max_wait_seconds: 60
    output_format: json
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Step dataclasses
# ---------------------------------------------------------------------------

VALID_ACTIONS: frozenset[str] = frozenset(
    {
        "open_url",
        "wait_seconds",
        "wait_for_element",
        "click_element",
        "scroll_to_bottom",
        "scroll_to_element",
        "switch_to_new_tab",
        "extract_current_url",
        "extract_link_href",
        "extract_page_title",
    }
)

VALID_SELECTOR_TYPES: frozenset[str] = frozenset(
    {"css", "xpath", "id", "text"}
)

VALID_OUTPUT_FORMATS: frozenset[str] = frozenset({"json", "human"})


class ConfigError(ValueError):
    """Raised when a workflow config is missing required fields or has invalid values."""


@dataclass
class StepConfig:
    """Represents a single workflow step.

    Attributes:
        action: The step action name (must be in :data:`VALID_ACTIONS`).
        url: Used by ``open_url`` action.
        seconds: Used by ``wait_seconds`` action.
        selector_type: How the selector is interpreted (``css``, ``xpath``, ``id``, ``text``).
        selector: The selector expression.
        timeout: Per-step explicit-wait override.
        label: Optional human-friendly label for logging.
        store_as: Variable name to store extracted values under.
    """

    action: str
    url: str = ""
    seconds: float = 0.0
    selector_type: str = "css"
    selector: str = ""
    timeout: int | None = None
    label: str = ""
    store_as: str = ""

    def __post_init__(self) -> None:
        if self.action not in VALID_ACTIONS:
            raise ConfigError(
                f"Unknown action {self.action!r}. Valid actions: {sorted(VALID_ACTIONS)}"
            )
        if self.selector_type not in VALID_SELECTOR_TYPES:
            raise ConfigError(
                f"Unknown selector_type {self.selector_type!r}. "
                f"Valid types: {sorted(VALID_SELECTOR_TYPES)}"
            )


@dataclass
class WorkflowConfig:
    """Top-level workflow configuration.

    Attributes:
        name: Human-readable workflow identifier.
        start_url: Initial URL to navigate to.
        steps: Ordered list of :class:`StepConfig` objects.
        expected_final_domain: Optional domain the final URL should belong to.
        max_wait_seconds: Upper bound on the total workflow wall-clock time.
        output_format: ``"json"`` or ``"human"`` (default).
        headless: Run browser in headless mode.
        timeout: Default per-step timeout in seconds.
        retries: Default number of retries for click/find operations.
    """

    name: str
    start_url: str
    steps: list[StepConfig] = field(default_factory=list)
    expected_final_domain: str = ""
    max_wait_seconds: int = 120
    output_format: str = "human"
    headless: bool = True
    timeout: int = 30
    retries: int = 3

    def __post_init__(self) -> None:
        if not self.name:
            raise ConfigError("Workflow 'name' must not be empty.")
        if not self.start_url:
            raise ConfigError("Workflow 'start_url' must not be empty.")
        if self.output_format not in VALID_OUTPUT_FORMATS:
            raise ConfigError(
                f"Invalid output_format {self.output_format!r}. "
                f"Choose one of: {sorted(VALID_OUTPUT_FORMATS)}"
            )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_step(raw: dict[str, Any]) -> StepConfig:
    """Convert a raw dictionary into a :class:`StepConfig`.

    Args:
        raw: A plain dictionary, typically loaded from YAML/JSON.

    Returns:
        A validated :class:`StepConfig`.

    Raises:
        ConfigError: If required fields are missing or invalid.
    """
    action = raw.get("action", "")
    if not action:
        raise ConfigError(f"Step is missing 'action' field: {raw}")
    return StepConfig(
        action=str(action),
        url=str(raw.get("url", "")),
        seconds=float(raw.get("seconds", 0.0)),
        selector_type=str(raw.get("selector_type", "css")),
        selector=str(raw.get("selector", "")),
        timeout=int(raw["timeout"]) if "timeout" in raw else None,
        label=str(raw.get("label", "")),
        store_as=str(raw.get("store_as", "")),
    )


def _parse_workflow(raw: dict[str, Any]) -> WorkflowConfig:
    """Convert a raw dictionary into a :class:`WorkflowConfig`.

    Args:
        raw: A plain dictionary loaded from the config file.

    Returns:
        A validated :class:`WorkflowConfig`.

    Raises:
        ConfigError: If required top-level fields are missing or invalid.
    """
    name = raw.get("name", "")
    start_url = raw.get("start_url", "")
    raw_steps = raw.get("steps", [])
    if not isinstance(raw_steps, list):
        raise ConfigError("'steps' must be a list.")
    steps = [_parse_step(s) for s in raw_steps]

    return WorkflowConfig(
        name=str(name),
        start_url=str(start_url),
        steps=steps,
        expected_final_domain=str(raw.get("expected_final_domain", "")),
        max_wait_seconds=int(raw.get("max_wait_seconds", 120)),
        output_format=str(raw.get("output_format", "human")),
        headless=bool(raw.get("headless", True)),
        timeout=int(raw.get("timeout", 30)),
        retries=int(raw.get("retries", 3)),
    )


def load_config(path: str | Path) -> WorkflowConfig:
    """Load and validate a workflow config from a YAML or JSON file.

    Args:
        path: Path to the ``.yaml``, ``.yml``, or ``.json`` config file.

    Returns:
        A validated :class:`WorkflowConfig`.

    Raises:
        ConfigError: If the file cannot be parsed or fails validation.
        FileNotFoundError: If *path* does not exist.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    suffix = config_path.suffix.lower()
    text = config_path.read_text(encoding="utf-8")

    try:
        if suffix in {".yaml", ".yml"}:
            raw = yaml.safe_load(text)
        elif suffix == ".json":
            raw = json.loads(text)
        else:
            raise ConfigError(
                f"Unsupported config file extension {suffix!r}. Use .yaml, .yml, or .json."
            )
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Failed to parse config file {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Config file must contain a YAML/JSON mapping at the top level.")

    logger.debug("Loaded config from %s", config_path)
    return _parse_workflow(raw)


def validate_config(path: str | Path) -> list[str]:
    """Validate a config file and return a list of error messages.

    An empty list means the config is valid.

    Args:
        path: Path to the config file.

    Returns:
        A (possibly empty) list of human-readable error messages.
    """
    errors: list[str] = []
    try:
        load_config(path)
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
    return errors


# ---------------------------------------------------------------------------
# Sample config
# ---------------------------------------------------------------------------

SAMPLE_CONFIG: dict[str, Any] = {
    "name": "two-step-redirect-example",
    "start_url": "https://example.com/start",
    "expected_final_domain": "example.com",
    "max_wait_seconds": 60,
    "output_format": "human",
    "headless": True,
    "timeout": 30,
    "retries": 3,
    "steps": [
        {
            "action": "open_url",
            "url": "https://example.com/start",
            "label": "Open landing page",
        },
        {
            "action": "wait_for_element",
            "selector_type": "css",
            "selector": "#continue-btn",
            "timeout": 15,
            "label": "Wait for continue button",
        },
        {
            "action": "click_element",
            "selector_type": "css",
            "selector": "#continue-btn",
            "label": "Click continue",
        },
        {
            "action": "wait_seconds",
            "seconds": 5,
            "label": "Countdown wait",
        },
        {
            "action": "wait_for_element",
            "selector_type": "css",
            "selector": "a#final-link",
            "timeout": 20,
            "label": "Wait for final link",
        },
        {
            "action": "extract_link_href",
            "selector_type": "css",
            "selector": "a#final-link",
            "store_as": "final_url",
            "label": "Extract final destination URL",
        },
        {
            "action": "extract_current_url",
            "store_as": "resolved_url",
            "label": "Capture current URL",
        },
        {
            "action": "extract_page_title",
            "store_as": "page_title",
            "label": "Capture page title",
        },
    ],
}
