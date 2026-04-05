"""Tests for config parsing and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.config import (
    ConfigError,
    StepConfig,
    WorkflowConfig,
    load_config,
    validate_config,
    SAMPLE_CONFIG,
)


# ---------------------------------------------------------------------------
# StepConfig tests
# ---------------------------------------------------------------------------


class TestStepConfig:
    def test_valid_step_css(self):
        step = StepConfig(action="click_element", selector_type="css", selector="#btn")
        assert step.action == "click_element"
        assert step.selector_type == "css"

    def test_valid_step_open_url(self):
        step = StepConfig(action="open_url", url="https://example.com")
        assert step.url == "https://example.com"

    def test_valid_step_wait_seconds(self):
        step = StepConfig(action="wait_seconds", seconds=5.0)
        assert step.seconds == 5.0

    def test_invalid_action_raises(self):
        with pytest.raises(ConfigError, match="Unknown action"):
            StepConfig(action="teleport")

    def test_invalid_selector_type_raises(self):
        with pytest.raises(ConfigError, match="Unknown selector_type"):
            StepConfig(action="click_element", selector_type="magic")

    def test_all_valid_actions(self):
        from src.config import VALID_ACTIONS

        for action in VALID_ACTIONS:
            step = StepConfig(action=action)
            assert step.action == action

    def test_all_valid_selector_types(self):
        from src.config import VALID_SELECTOR_TYPES

        for st in VALID_SELECTOR_TYPES:
            step = StepConfig(action="click_element", selector_type=st)
            assert step.selector_type == st

    def test_optional_fields_default(self):
        step = StepConfig(action="scroll_to_bottom")
        assert step.url == ""
        assert step.seconds == 0.0
        assert step.timeout is None
        assert step.label == ""
        assert step.store_as == ""

    def test_label_and_store_as(self):
        step = StepConfig(
            action="extract_current_url",
            label="my label",
            store_as="captured_url",
        )
        assert step.label == "my label"
        assert step.store_as == "captured_url"


# ---------------------------------------------------------------------------
# WorkflowConfig tests
# ---------------------------------------------------------------------------


class TestWorkflowConfig:
    def test_valid_minimal_config(self):
        cfg = WorkflowConfig(name="test", start_url="https://example.com")
        assert cfg.name == "test"
        assert cfg.start_url == "https://example.com"
        assert cfg.steps == []
        assert cfg.output_format == "human"

    def test_empty_name_raises(self):
        with pytest.raises(ConfigError, match="name"):
            WorkflowConfig(name="", start_url="https://example.com")

    def test_empty_start_url_raises(self):
        with pytest.raises(ConfigError, match="start_url"):
            WorkflowConfig(name="test", start_url="")

    def test_invalid_output_format_raises(self):
        with pytest.raises(ConfigError, match="output_format"):
            WorkflowConfig(
                name="test",
                start_url="https://example.com",
                output_format="xml",
            )

    def test_defaults(self):
        cfg = WorkflowConfig(name="n", start_url="https://x.com")
        assert cfg.headless is True
        assert cfg.timeout == 30
        assert cfg.retries == 3
        assert cfg.max_wait_seconds == 120

    def test_steps_list(self):
        steps = [StepConfig(action="open_url", url="https://example.com")]
        cfg = WorkflowConfig(name="n", start_url="https://example.com", steps=steps)
        assert len(cfg.steps) == 1


# ---------------------------------------------------------------------------
# load_config tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_load_valid_yaml(self, tmp_path: Path):
        data = {
            "name": "test-workflow",
            "start_url": "https://example.com",
            "steps": [
                {"action": "open_url", "url": "https://example.com"},
                {"action": "wait_seconds", "seconds": 2},
            ],
        }
        cfg_file = tmp_path / "wf.yaml"
        cfg_file.write_text(yaml.dump(data), encoding="utf-8")
        cfg = load_config(cfg_file)
        assert cfg.name == "test-workflow"
        assert len(cfg.steps) == 2

    def test_load_valid_json(self, tmp_path: Path):
        data = {
            "name": "json-workflow",
            "start_url": "https://example.com",
            "steps": [],
        }
        cfg_file = tmp_path / "wf.json"
        cfg_file.write_text(json.dumps(data), encoding="utf-8")
        cfg = load_config(cfg_file)
        assert cfg.name == "json-workflow"

    def test_load_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_load_unsupported_extension_raises(self, tmp_path: Path):
        f = tmp_path / "wf.toml"
        f.write_text("name = 'test'", encoding="utf-8")
        with pytest.raises(ConfigError, match="Unsupported"):
            load_config(f)

    def test_load_invalid_yaml_raises(self, tmp_path: Path):
        f = tmp_path / "bad.yaml"
        f.write_text("::invalid: yaml: content::::", encoding="utf-8")
        with pytest.raises(ConfigError, match="Failed to parse"):
            load_config(f)

    def test_load_non_mapping_raises(self, tmp_path: Path):
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="mapping"):
            load_config(f)

    def test_load_sample_config(self, tmp_path: Path):
        """The built-in SAMPLE_CONFIG should round-trip through load_config."""
        cfg_file = tmp_path / "sample.yaml"
        cfg_file.write_text(
            yaml.dump(SAMPLE_CONFIG, sort_keys=False), encoding="utf-8"
        )
        cfg = load_config(cfg_file)
        assert cfg.name == SAMPLE_CONFIG["name"]
        assert len(cfg.steps) == len(SAMPLE_CONFIG["steps"])

    def test_load_configs_dir_samples(self):
        """All YAML files in configs/ must be loadable without errors."""
        configs_dir = Path(__file__).parent.parent / "configs"
        for yaml_file in configs_dir.glob("*.yaml"):
            cfg = load_config(yaml_file)
            assert cfg.name  # non-empty name

    def test_step_with_timeout_override(self, tmp_path: Path):
        data = {
            "name": "t",
            "start_url": "https://x.com",
            "steps": [{"action": "wait_for_element", "selector": "#x", "timeout": 42}],
        }
        f = tmp_path / "t.yaml"
        f.write_text(yaml.dump(data), encoding="utf-8")
        cfg = load_config(f)
        assert cfg.steps[0].timeout == 42


# ---------------------------------------------------------------------------
# validate_config tests
# ---------------------------------------------------------------------------


class TestValidateConfig:
    def test_valid_file_returns_empty_list(self, tmp_path: Path):
        data = {"name": "w", "start_url": "https://example.com", "steps": []}
        f = tmp_path / "valid.yaml"
        f.write_text(yaml.dump(data), encoding="utf-8")
        errors = validate_config(f)
        assert errors == []

    def test_missing_file_returns_error(self, tmp_path: Path):
        errors = validate_config(tmp_path / "ghost.yaml")
        assert len(errors) == 1
        assert "not found" in errors[0].lower() or "no such" in errors[0].lower()

    def test_invalid_action_returns_error(self, tmp_path: Path):
        data = {
            "name": "w",
            "start_url": "https://example.com",
            "steps": [{"action": "bad_action"}],
        }
        f = tmp_path / "bad.yaml"
        f.write_text(yaml.dump(data), encoding="utf-8")
        errors = validate_config(f)
        assert errors
