# Access Control Security Testing Framework

An AI-powered web security testing framework that automatically crawls websites under multiple user roles, cross-examines access control boundaries, and generates a professional PDF report with OWASP-aligned risk ratings and recommendations.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Module Reference](#module-reference)
  - [main.py](#mainpy)
  - [crawler.py](#crawlerpy)
  - [cross_examine.py](#cross_examinepy)
  - [ai_engine.py](#ai_enginepy)
  - [generate_report.py](#generate_reportpy)
  - [auto_recommendation.py](#auto_recommendationpy)
- [Output Files](#output-files)
- [Configuration](#configuration)
- [Requirements](#requirements)

---

## Overview

The framework performs the following pipeline end-to-end:

1. **Crawl** - A headless Chrome browser spiders the target site once per configured role, discovering links, forms, and API endpoints.
2. **Cross-Examine** - Each role's session is replayed against every other role's exclusive URLs to detect broken access control.
3. **AI Analysis** - An LLM compares DOM snapshots semantically and generates mutated (fuzzed) URLs for negative testing.
4. **Report** - Results are written to a JSON file and rendered as a styled PDF containing an executive summary, OWASP risk matrix, per-violation details, and OWASP-sourced recommendations.

---

## Architecture

```
main.py                  ← Orchestrator: configures roles, runs crawl → cross-examine → report
  │
  ├── crawler.py         ← Selenium-based web crawler (one instance per role)
  │
  ├── cross_examine.py   ← Access-control cross-examination engine
  │     └── ai_engine.py ← LLM-backed semantic comparison & parameter mutation
  │
  ├── generate_report.py ← PDF report generator (fpdf) with OWASP risk ratings
  │     └── Recommendations.xlsx  ← Lookup table for per-violation recommendations
  │
  └── auto_recommendation.py ← Scrapes OWASP Top 10 pages to populate Recommendations.xlsx
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> Chrome/Chromium and a matching ChromeDriver must be installed and on your PATH.

### 2. Set your LLM API key

The default configuration uses Groq (free tier). Export one of:

```bash
export GROQ_API_KEY="gsk_..."          # Groq  (default in main.py)
export OPENAI_API_KEY="sk-..."         # OpenAI
export OPENROUTER_API_KEY="sk-or-..."  # OpenRouter
```

### 3. (Optional) Populate the recommendations spreadsheet

```bash
python auto_recommendation.py
```

This fetches the latest "How to Prevent" sections from OWASP Top 10 pages and writes them into `Recommendations.xlsx`. The file is auto-created if it does not exist.

### 4. Run the scan

Edit the `ROLES` list and `BASE_URL` in `main.py` to match your target, then:

```bash
python main.py
```

### 5. View results

- `access_control_report.json` — Machine-readable findings
- `report_for_<domain>.pdf` — Styled PDF report

---

## Module Reference

### `main.py`

Entry point that ties the entire pipeline together.

| Constant | Purpose |
|---|---|
| `BASE_URL` | Target website root URL |
| `ROLES` | List of `{role, username, password}` dicts defining the accounts to test |

**Workflow:**

1. Initialises an `AIEngine` with a `GroqProvider`.
2. For each role, creates a `WebCrawler`, discovers the login form, logs in (if credentials exist), and performs a breadth-first crawl.
3. Passes all crawlers and the AI engine to `CrossExaminar.perform_examination()`.
4. Saves findings via `CrossExaminar.generate_report()`.
5. Calls `generate_pdf()` to render the PDF.

---

### `crawler.py`

Selenium-based headless Chrome crawler. One instance is created per user role.

#### Class: `WebCrawler`

```python
WebCrawler(base_url: str, role: str, username: str, password: str)
```

**Attributes:**

| Attribute | Type | Description |
|---|---|---|
| `role` | `str` | Role label (e.g. `"admin"`, `"guest"`) |
| `username` / `password` | `str` | Login credentials (empty string = guest) |
| `browser` | `webdriver.Chrome` | Headless Chrome instance with performance logging |
| `base_url` | `str` | Root URL of the target site |
| `login_url` | `str` | Auto-detected login page URL |
| `currentpage` | `str` | URL the browser is currently on |
| `url_collections` | `dict[str, list]` | Links discovered on each visited page |
| `forms_collections` | `dict[str, list]` | Forms discovered on each visited page |
| `loginform_collections` | `dict` | Detected login form `BeautifulSoup` tags keyed by URL |
| `api_collections` | `list[dict]` | API endpoints detected from browser network logs |
| `accessed_url` | `list[str]` | URLs that returned HTTP < 400 |
| `html_snapshots` | `dict[str, str]` | Full HTML source keyed by URL (ground-truth for AI comparison) |

**Key Methods:**

| Method | Description |
|---|---|
| `visit_page(url=None)` | Navigate to a URL (defaults to `base_url`), scrape links/forms/APIs, store HTML snapshot |
| `login()` | Auto-fill detected login form and submit. Returns the post-login URL |
| `get_links_from_page()` | Parse `<a href>` tags and normalise to absolute URLs |
| `get_forms_from_page()` | Parse `<form>` tags; auto-detect login forms via `is_login_form()` |
| `get_api_from_page()` | Inspect Chrome performance logs for XHR/fetch API calls matching known patterns |
| `is_login_form(form_element)` | Heuristic check: password field + username/email field + ≤3 visible inputs |
| `get_status_code(url)` | Execute an in-browser `fetch(HEAD)` to return the HTTP status code |
| `convert_to_full_url(link)` | Resolve relative/hash/path links to absolute URLs |
| `store_html_snapshot()` | Save `browser.page_source` for the current URL |
| `get_stored_html(url)` | Retrieve previously stored HTML for a URL |
| `get_page_content(url)` | Navigate to URL and return `(status_code, html_source)` |

---

### `cross_examine.py`

Core testing engine that compares access boundaries across roles.

#### Class: `Violation`

Data class representing a single access-control breach.

| Field | Description |
|---|---|
| `url` | The vulnerable endpoint |
| `owner_role` | The role that legitimately owns the resource |
| `tester_role` | The role that was able to access it |
| `type` | Violation category (see below) |
| `severity` | `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` |
| `reasoning` | Human-readable explanation |
| `status_code` | HTTP status returned to the tester |
| `confidence` | `high` / `medium` / `low` |

**Violation Types Produced:**

| Type | Source |
|---|---|
| `VERTICAL_PRIVILEGE_ESCALATION` | Standard exam — admin URL keywords |
| `HORIZONTAL_PRIVILEGE_ESCALATION` | Standard exam — same-level roles |
| `API_AUTHORIZATION_BYPASS` | Standard exam — API URL keywords |
| `USER_DATA_ACCESS` | Standard exam — user data URL keywords |
| `BROKEN_ACCESS_CONTROL` | Standard exam — general fallback |
| `IDOR_HORIZONTAL` | Standard exam & AI exam — same-privilege IDOR |
| `VERTICAL_PE` | AI exam — lower privilege accessing higher privilege data |
| `MUTATION_<ATTACK_TYPE>` | Mutation exam — AI-generated fuzzed URLs |

#### Class: `CrossExaminar`

```python
CrossExaminar(crawlers: List[WebCrawler], ai_engine: Optional[AIEngine] = None)
```

**Role Hierarchy:**

Built-in privilege levels (`_levels` dict): `guest=0`, `user/customer=1`, `admin/manager/test=2`, `superadmin=3`. Unknown roles default to `0`.

**`perform_examination()`** — Runs three phases in order:

| Phase | Method | Description |
|---|---|---|
| 1 — Standard | `_perform_standard_examination()` | Replays each higher-privilege role's exclusive URLs with every lower-privilege session. Flags HTTP 2xx responses as violations. Also tests same-level pairs for IDOR. |
| 2 — AI Semantic | `_perform_ai_examination()` | For URLs returning HTTP 2xx, compares the DOM content between the owner's ground-truth snapshot and the tester's response using the AI engine. Catches cases where the server returns 200 but shows a different/empty page. |
| 3 — Mutation | `_perform_mutation_examination()` | Asks the AI engine to generate fuzzed/mutated URLs (e.g. `/api/user/profile` → `/api/admin/profile`), then replays them with every role's session. |

**`generate_report(output_file)`** — Writes a JSON report with summary statistics, all violations, and raw test results.

---

### `ai_engine.py`

LLM integration layer providing semantic analysis and intelligent fuzzing.

#### LLM Providers

All providers implement the abstract `LLMProvider.generate(prompt) -> str` interface:

| Class | Backend | Default Model | Env Variable |
|---|---|---|---|
| `OpenAIProvider` | OpenAI API | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `GroqProvider` | Groq API | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| `OpenRouterProvider` | OpenRouter API | `openrouter/free` | `OPENROUTER_API_KEY` |
| `OpenAICompatibleProvider` | Any OpenAI-compatible endpoint | `gpt-4o-mini` | `OPENAI_API_KEY` |

#### Class: `AIEngine`

```python
AIEngine(llm_provider: Optional[LLMProvider] = None)
```

**Feature 1 — Semantic State Comparison:**

| Method | Description |
|---|---|
| `compare_dom_snapshots(user_a_html, user_b_html, ...)` | Extracts page summaries (title, headings, form fields, PII indicators), computes text similarity. If >95% similar → same data. Otherwise, sends both summaries to the LLM for semantic comparison. Returns `contains_same_data`, `confidence`, `reasoning`, etc. |
| `batch_compare_snapshots(comparisons)` | Processes a list of comparison tuples sequentially. |

**Feature 2 — Intelligent Parameter Mutation (AI Fuzzing):**

| Method | Description |
|---|---|
| `generate_parameter_mutations(url, method, ...)` | Sends a single URL to the LLM to generate IDOR, privilege escalation, hidden endpoint, and debug mutation suggestions. |
| `batch_generate_parameter_mutations(discovered_urls)` | Sends all discovered URLs in a single prompt for efficiency. |
| `generate_fuzzing_campaign(discovered_urls, roles)` | Orchestrates batch mutation generation and organises results by attack type (`idor_tests`, `privilege_escalation_tests`, `hidden_endpoint_tests`, `debug_tests`). |

If the LLM fails to produce valid JSON, the engine falls back to rule-based mutations (`_generate_fallback_mutations`), which apply common path replacements and sequential ID probing.

---

### `generate_report.py`

Generates a professional PDF report from the JSON findings using `fpdf`.

#### Key Functions

| Function | Description |
|---|---|
| `generate_pdf(base_url, json_path, output_path)` | Main entry point. Loads the JSON report and renders every section of the PDF. |
| `generate_recommendations(violations)` | Looks up each violation's type in `Recommendations.xlsx`, matches by URL keyword (or falls back to `"default"`), and returns contextualised recommendation strings. Maps internal types like `VERTICAL_PE` and `IDOR_HORIZONTAL` to `BROKEN_ACCESS_CONTROL` for lookup. |
| `owasp_risk_rating(likelihood, impact)` | Computes an OWASP risk level from 1-9 likelihood/impact scores using a 3×3 matrix. |
| `draw_security_score(pdf, violations, summary)` | Renders the per-violation risk table, overall risk summary bar, and the full OWASP Likelihood × Impact matrix. |

**PDF Sections:**

1. Executive Summary (test counts, severity breakdown)
2. Roles Tested (pages crawled, URLs accessible, APIs found per role)
3. Detected Violations (detailed cards with severity colour coding)
4. OWASP Risk Rating (per-violation table + risk matrix)
5. All Test Results (full table of every URL tested)
6. Recommendations (sourced from `Recommendations.xlsx`)

---

### `auto_recommendation.py`

Standalone script that scrapes the latest OWASP Top 10 "How to Prevent" sections and populates `Recommendations.xlsx`.

```bash
python auto_recommendation.py
```

**OWASP Sources Scraped:**

| Violation Type | OWASP Page |
|---|---|
| `BROKEN_ACCESS_CONTROL` | A01:2025 — Broken Access Control |
| `MISSING_AUTHENTICATION` | A07:2025 — Authentication Failures |
| `SECURITY_MISCONFIGURATION` | A02:2025 — Security Misconfiguration |
| `SENSITIVE_DATA_EXPOSURE` | A04:2025 — Cryptographic Failures |

**How it works:**

1. Creates `Recommendations.xlsx` if it does not exist (with headers and an instructional sheet).
2. For each OWASP source, fetches the page and extracts `<li>` items under the "How to Prevent" heading.
3. Maps each recommendation to a keyword (`api`, `admin`, `password`, `token`, `log`, etc.) based on content heuristics; unmatched items get the `default` keyword.
4. Removes old rows for that violation type and inserts fresh ones with formatting.

---

## Output Files

| File | Description |
|---|---|
| `access_control_report.json` | Raw JSON with `summary`, `violations`, and `all_results` arrays |
| `report_for_<domain>.pdf` | Styled PDF report (auto-named from the target domain) |
| `Recommendations.xlsx` | OWASP recommendation lookup table (auto-generated by `auto_recommendation.py`) |

---

## Configuration

### Target & Roles (`main.py`)

```python
BASE_URL = "http://testphp.vulnweb.com/"

ROLES = [
    {"role": "test",  "username": "test", "password": "test"},
    {"role": "guest", "username": "",     "password": ""},
]
```

- Add more roles to test horizontal (IDOR) and vertical privilege escalation.
- The `role` string must match an entry in `CrossExaminar._levels` or it defaults to privilege level 0.

### Role Hierarchy (`cross_examine.py`)

```python
_levels = {
    "guest":      0,
    "user":       1,
    "customer":   1,
    "customer_b": 1,
    "test":       2,
    "admin":      2,
    "manager":    2,
    "superadmin": 3,
}
```

Extend this dict to add custom roles.

### LLM Provider (`main.py`)

Switch providers by changing the instantiation:

```python
from ai_engine import AIEngine, GroqProvider, OpenAIProvider, OpenRouterProvider

aiEngine = AIEngine(llm_provider=GroqProvider())           # Groq (default)
aiEngine = AIEngine(llm_provider=OpenAIProvider())         # OpenAI
aiEngine = AIEngine(llm_provider=OpenRouterProvider())     # OpenRouter
```

---

## Requirements

- **Python** 3.10+
- **Google Chrome** / Chromium + ChromeDriver
- One of: Groq, OpenAI, or OpenRouter API key

### Python Packages

See `requirements.txt`. Core dependencies:

| Package | Purpose |
|---|---|
| `selenium` | Headless browser automation |
| `beautifulsoup4` | HTML parsing |
| `groq` / `openai` / `openrouter` | LLM API clients |
| `fpdf` | PDF generation |
| `openpyxl` | Excel read/write for recommendations |
| `pandas` | DataFrame operations for recommendation lookup |
| `requests` | HTTP fetching for OWASP scraper |
