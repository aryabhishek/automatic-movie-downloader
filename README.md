# automatic-movie-downloader

> **Important – Ethical & Legal Use Only**
> This tool is built exclusively for legitimate, authorized use cases: navigating
> multi-step redirect chains, waiting for countdown timers, clicking buttons, and
> extracting the final resolved URL on **websites you own or have explicit
> permission to test**. Do not use it to bypass CAPTCHAs, authentication walls,
> paywalls, or anti-bot protections. Do not automate access to copyrighted
> content or piracy-related flows.

---

A robust, headless browser automation tool that takes an input URL, follows a
configurable sequence of interactions, waits for time-based unlocks, clicks
buttons, handles new tabs, and returns the final destination URL together with
page metadata.  Site-specific logic lives in **YAML / JSON config files** — no
code changes required for new workflows.

## Features

- Headless Chrome (via Selenium 4) with optional visible-window debug mode
- Configurable multi-step workflows (YAML or JSON)
- Explicit waits instead of blind sleeps
- Automatic retries for transient failures
- Tab switching support
- Value extraction (current URL, link href, page title)
- JSON or human-readable output
- Full CLI powered by [Typer](https://typer.tiangolo.com/)
- Structured logging with timestamps
- Comprehensive pytest test suite (no browser required for tests)

---

## Project Structure

```
.
├── src/
│   ├── __init__.py
│   ├── browser.py       # Headless Chrome wrapper
│   ├── config.py        # Dataclass config models + YAML/JSON parsing
│   ├── steps.py         # Step handlers (open_url, click_element, …)
│   ├── engine.py        # Workflow execution engine
│   └── cli.py           # Typer CLI
├── tests/
│   ├── test_config.py   # Config parsing & validation tests
│   ├── test_steps.py    # Step handler unit tests
│   └── test_engine.py   # Engine integration tests (mocked browser)
├── configs/
│   └── sample_redirect.yaml   # Two-step redirect sample workflow
├── examples/
│   ├── new_tab_redirect.yaml  # New-tab redirect example
│   └── xpath_selector.yaml    # XPath selector example
├── pyproject.toml
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.11+
- Google Chrome or Chromium installed
- Matching `chromedriver` on your `PATH` (or install via `webdriver-manager`)

### Install

```bash
# 1. Clone the repository
git clone https://github.com/aryabhishek/automatic-movie-downloader.git
cd automatic-movie-downloader

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install the package and runtime dependencies
pip install -e .

# 4. Install dev / test dependencies
pip install -e ".[dev]"
```

---

## CLI Usage

The CLI entry point is `amd` (or `python -m src.cli`).

### `resolve` — run a workflow and print the final URL

```bash
amd resolve https://example.com/start --config configs/sample_redirect.yaml
```

With JSON output:

```bash
amd resolve https://example.com/start \
    --config configs/sample_redirect.yaml \
    --format json
```

With debug logging:

```bash
amd resolve https://example.com/start \
    --config configs/sample_redirect.yaml \
    --verbose
```

### `validate-config` — check a config file without opening a browser

```bash
amd validate-config configs/sample_redirect.yaml
```

### `debug` — run with a visible browser window

```bash
amd debug https://example.com/start --config configs/sample_redirect.yaml
```

### `export-sample-config` — dump a sample config to stdout or a file

```bash
# Print to stdout (YAML by default)
amd export-sample-config

# Save to a file as JSON
amd export-sample-config --format json --output my_workflow.json
```

---

## Workflow Config Reference

Configs are YAML or JSON files.  The top-level keys are:

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `name` | string | ✓ | — | Human-readable workflow name |
| `start_url` | string | ✓ | — | Initial URL to load |
| `steps` | list | ✓ | `[]` | Ordered list of step objects |
| `expected_final_domain` | string | | `""` | Warn if final URL is not on this domain |
| `max_wait_seconds` | int | | `120` | Total timeout cap |
| `output_format` | string | | `"human"` | `"human"` or `"json"` |
| `headless` | bool | | `true` | Run Chrome in headless mode |
| `timeout` | int | | `30` | Default per-step explicit-wait (seconds) |
| `retries` | int | | `3` | Retry count for click/find operations |

### Step fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `action` | string | ✓ | — | One of the supported actions below |
| `url` | string | | `""` | URL for `open_url` action |
| `seconds` | float | | `0` | Seconds for `wait_seconds` |
| `selector_type` | string | | `"css"` | `css`, `xpath`, `id`, or `text` |
| `selector` | string | | `""` | Selector expression |
| `timeout` | int | | `null` | Per-step timeout override |
| `label` | string | | `""` | Description for logs |
| `store_as` | string | | `""` | Key to store extracted values under |

### Supported actions

| Action | Description |
|--------|-------------|
| `open_url` | Navigate to `url` |
| `wait_seconds` | Sleep for `seconds` |
| `wait_for_element` | Explicit wait until element is visible |
| `click_element` | Wait for element then click it |
| `scroll_to_bottom` | Scroll page to bottom |
| `scroll_to_element` | Scroll element into view |
| `switch_to_new_tab` | Wait for and switch to a new tab |
| `extract_current_url` | Store current URL in context |
| `extract_link_href` | Store `href` of a link element |
| `extract_page_title` | Store page `<title>` in context |

### Supported selector types

| Type | Maps to Selenium `By` | Example |
|------|-----------------------|---------|
| `css` | `By.CSS_SELECTOR` | `"#my-btn"` |
| `xpath` | `By.XPATH` | `"//button[text()='Go']"` |
| `id` | `By.ID` | `"submit-form"` |
| `text` | `By.PARTIAL_LINK_TEXT` | `"Click here"` |

---

## Example Config

```yaml
name: two-step-redirect-example
start_url: https://example.com/start
expected_final_domain: example.com
max_wait_seconds: 60
output_format: human
headless: true
timeout: 30
retries: 3

steps:
  - action: open_url
    url: https://example.com/start
    label: "Open landing page"

  - action: wait_for_element
    selector_type: css
    selector: "#continue-btn"
    timeout: 15
    label: "Wait for continue button"

  - action: click_element
    selector_type: css
    selector: "#continue-btn"
    label: "Click continue"

  - action: wait_seconds
    seconds: 5
    label: "Countdown wait"

  - action: extract_link_href
    selector_type: css
    selector: "a#final-link"
    store_as: final_url
    label: "Extract final URL"

  - action: extract_current_url
    store_as: resolved_url

  - action: extract_page_title
    store_as: page_title
```

---

## Adding a New Workflow

1. Create a new YAML file in `configs/` (or anywhere on your filesystem).
2. Fill in the `name`, `start_url`, and `steps` according to the reference above.
3. Run `amd validate-config your_config.yaml` to check for errors.
4. Run `amd resolve <url> --config your_config.yaml` to execute.

No Python changes are required unless you need a brand-new *action* type.  To
add a new action:

1. Write a handler function `execute_<action>(step, browser, context)` in
   `src/steps.py`.
2. Register it in the `STEP_HANDLERS` dict at the bottom of that file.
3. Add the action name to `VALID_ACTIONS` in `src/config.py`.
4. Add tests in `tests/test_steps.py`.

---

## Running Tests

```bash
# All tests (no real browser required — browser is mocked)
pytest

# With verbose output
pytest -v

# One file
pytest tests/test_config.py -v
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `chromedriver` not found | Install via `pip install webdriver-manager` and wrap the `Service()` call, or download manually and place on `PATH` |
| `ElementNotFoundError` | Increase `timeout` or check that the selector is correct in a headed (`debug`) run |
| Workflow fails on first step | Make sure the `start_url` is reachable and the site does not block headless Chrome |
| Blank page title | Some SPAs populate the title asynchronously; add a `wait_for_element` step for a known element before `extract_page_title` |

---

## Limitations

- Only Chrome / Chromium is supported (Firefox support can be added by extending `browser.py`).
- JavaScript-heavy pages may need extra `wait_for_element` steps.
- The tool does not handle CAPTCHAs, logins, or other access controls by design.
- Rate limiting is the caller's responsibility.

---

## License

MIT
