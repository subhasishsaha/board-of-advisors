# 🏛️ Board of Advisors: Autonomous Multi-Agent Decision Council

An autonomous executive advisory board designed to help founders, leaders, and decision-makers navigate high-stakes strategic, financial, technical, and governance dilemmas.

Powered by **Gemini 3.8 Flash** with **medium reasoning effort**, orchestrated using **Antigravity CLI (`agy`)** in detached mode.

---

## 🌟 Key Features

1. **Dynamic, Problem-Tailored Board Assembly**:
   - Rather than static predefined roles, the orchestrator analyzes your specific problem and dynamically convenes a bespoke board of specialist advisors (configurable up to 20, default max 10; typically 4–6) with complementary expertise, distinct personas, and opposing viewpoints tailored to the dilemma.
   - Each advisor is endowed with a realistic bio, specific cognitive biases, core beliefs, and an assigned `@tag` (e.g. `@Elena`, `@Marcus`, `@Victoria`, `@Tariq`).

2. **Adaptive Deliberation with Configurable Ceiling**:
   - **Adaptive Discussion**: Deliberation adapts to the complexity of the dilemma (default ceiling: 3 round tables; configurable per-session via `/set-round-tables`).
   - **Round 1 (Opening Assessments)**: Each advisor presents their domain perspective and poses sharp, direct questions to colleagues via `@mentions`.
   - **Round 2 (Cross-Examination)**: Advisors answer directed questions, stress-test peer assumptions, and navigate trade-offs. If consensus is reached early, the board can proceed directly to action plan synthesis.
   - **Round 3 (Mandatory Conclusion)**: In the final round, advisors receive a strict mandate: *this is the final round and they must come to a definitive conclusion*. Disagreements are reconciled into final verdicts.

3. **Autonomous Tagging & Dynamic Routing**:
   - Advisors dynamically tag other advisors with `@tags` to challenge them directly.
   - The orchestrator extracts mentions, routes directed inquiries, and gives priority speaking turns to tagged advisors so questions are answered head-on.

4. **Intelligent In-Deliberation User Inquiries**:
   - Advisors can tag `@User` when critical factual constraints, risk tolerances, or budget ceilings are needed.
   - The Board Chair intelligently evaluates the statement in full discussion context, filtering out rhetorical questions and debate banter, and only suspends the meeting when genuine blocker inputs are required from the user.

5. **Interactive Claude Code & Antigravity Style CLI**:
   - **Interactive Autocomplete**: Powered by `prompt_toolkit`, typing `/` opens an interactive dropdown menu of slash commands, and typing `@` autocompletes active advisor tags.
   - **Chaining Prevention**: Blocks command chaining (`//`, `&&`, `;`, concatenated slash commands) to guarantee predictable and secure execution.
   - **Options Menu**: Simply typing `/` displays a clean interactive options menu with single-key numeric (1–11) selection.

6. **Per-Advisor Persistent Memory**:
   - Each advisor maintains private long-term memory stored under `storage/memory/<advisor_id>.json`.
   - Remembers past stances, problem contexts, and impressions of fellow board members across sessions.

7. **Antigravity CLI Detached Execution**:
   - Every LLM agent turn is invoked via the `agy` CLI in detached, non-blocking mode (`stdin=subprocess.DEVNULL`, Windows no-window process creation).
   - Configurable model and reasoning effort at launch via `--model` and `--effort`.

---

## ⌨️ Command Shortcuts

| Command | Action |
| :--- | :--- |
| `/` or `/menu` | Open the interactive Slash Command menu with numeric selection |
| `/new [problem]` | Start a brand new session with a fresh tailored council |
| `/history` | Browse past deliberations; enter `#` to load or `d #` (e.g. `d 2`) to delete |
| `/delete <#>` | Delete a saved session by index or session ID |
| `/cls` | Clear current session slate in the active thread without starting a new session |
| `/set-max-agents <#>` | Set max dynamic advisors for this thread (1–20, default: 10) |
| `/set-round-tables <#>` | Set deliberation rounds for this thread (1–10, default: 3) |
| `/plan` | Reprint the consolidated Plan of Action |
| `/advisors` | View active board members, tags, and roles |
| `/memory` | Inspect advisors' persistent private memories and beliefs |
| `/help` | Show available commands and usage guide |
| `/exit` | Exit the council session |

---

## 🔒 Security Architecture

The application implements defense-in-depth security remediations:

- **SEC-01 (Path Traversal Protection on Sessions)**: Strict path containment validation (`is_relative_to(SESSIONS_DIR)`) and alphanumeric format sanitization on session IDs prevents directory traversal and arbitrary file deletion.
- **SEC-02 (Advisor Memory & Builder Traversal Defense)**: Identifier sanitization prevents directory traversal in memory file paths (`storage/memory/<clean_id>.json`) and ensures UI colors match strict safe token regexes.
- **SEC-03 (Invoker Parameter Validation)**: Strict regex validation on `--model`, allowed whitelist for `--effort` (`low`, `medium`, `high`, `max`), and validated positive integer timeouts prevent command-line flag injection.
- **SEC-04 (Executable Discovery Hardening)**: Antigravity CLI binary resolution rejects binaries inside the current working directory or repository root (CWE-426) to prevent untrusted binary hijacking.
- **SEC-05 (Prompt Injection & Delimiter Disarming)**: XML-like boundary tags (`</user_dilemma>`, `<discussion_transcript>`, etc.) in user inputs and transcripts are disarmed to enforce strict system prompt data boundaries.
- **SEC-06 (Rich Console Markup Escaping)**: All untrusted strings (names, roles, session snippets, error messages) are escaped with `rich.markup.escape()` before terminal rendering, preventing terminal injection and parser crashes.

---

## 🚀 Quickstart

### Prerequisites
- Python 3.10+
- Antigravity CLI (`agy`) installed and authenticated on your machine.

### 1. Environment Setup
The project uses the local `.venv` environment for all Python operations:

```powershell
# Activate the virtual environment
.\.venv\Scripts\activate
```

Dependencies (`rich`, `pyyaml`, `prompt-toolkit`, `pytest`, `pytest-asyncio`) can be installed or updated via:
```powershell
uv pip install -r requirements.txt --python .\.venv\Scripts\python.exe
```

### 2. Run the Board of Advisors
Launch the interactive terminal council:

```powershell
# Default model and effort
.\.venv\Scripts\python.exe main.py

# Custom model and reasoning effort
.\.venv\Scripts\python.exe main.py --model gemini-3.8-flash-medium --effort medium
```

CLI arguments:
- `-m, --model`: Model identifier (default: `gemini-3.8-flash-medium`)
- `-e, --effort`: Reasoning effort level (`low`, `medium`, `high`, `max`; default: `medium`)

---

## 🧪 Running Tests

The test suite uses `pytest` with `pytest-asyncio` for comprehensive asynchronous and security testing:

```powershell
# Run the full test suite
.\.venv\Scripts\python.exe -m pytest -v
```

All 53 tests cover:
- Slash command parsing, command chaining prevention, and autocomplete completer
- CLI argument parsing, thread configuration persistence (`max_agents`, `max_rounds`)
- Session management, loading, clear-slate (`/cls`), and deletion
- Chairperson user-inquiry evaluation logic
- Security validations (SEC-01 through SEC-06 path traversal, prompt injection, and markup escaping)

---

## 💬 Example Flow

1. **Enter Your Dilemma:**
   > *"Should our digital health startup partner with a large hospital network under an exclusive 3-year agreement, or continue selling directly to individual clinics to remain unencumbered?"*

2. **Dynamic Assembly:**
   The orchestrator analyzes the challenge and assembles:
   - `📈 Marcus Vance (@Marcus)` — General Partner, HealthTech VC (Cap table & unit economics)
   - `🏥 Dr. Elena Rostova (@Elena)` — Former Hospital System CSO (Hospital politics & clinical workflow)
   - `⚡ Tariq Al-Mansoor (@Tariq)` — VP of Growth (Bottom-up PLG & iteration velocity)
   - `⚖️ Victoria Chen, Esq. (@Victoria)` — Healthcare Regulatory & M&A Partner (Exclusivity traps & data rights)
   - `🛡️ Dr. Kwame Owusu (@Kwame)` — Chief Clinical Officer (Provider burnout & adoption friction)

3. **Multi-Stage Deliberation:**
   - **Round 1**: Opening perspectives and targeted tags.
   - **Round 2**: Cross-examination of exclusivity terms and alternative distribution paths.
   - **Round 3**: Concluding verdicts under the final-round mandate.

4. **Action Plan:**
   Synthesized master plan with kill-switch milestones, counter-offer strategy, and execution steps.

5. **Follow-Up:**
   Chat directly with the board (e.g. `"@Victoria what specific exclusivity clause must we reject?"`).

---

## 📂 Project Structure

```
board-of-advisors/
├── .venv/                   # Python virtual environment
├── config/
│   └── advisors.yaml        # Fallback advisor profiles
├── board/
│   ├── __init__.py          # Package exports
│   ├── advisor.py           # Advisor agent logic & round prompt construction
│   ├── advisor_builder.py   # Dynamic advisor JSON parser & sanitizer
│   ├── cli_completer.py     # Prompt-toolkit slash command & @tag autocomplete
│   ├── cli_ui.py            # Rich terminal chat panels, badges & formatting
│   ├── config.py            # CLI paths, model settings & directory constants
│   ├── invoker.py           # Detached Antigravity CLI (agy) runner
│   ├── memory.py            # Per-advisor persistent memory store
│   ├── orchestrator.py      # Dynamic assembly, debate routing & synthesis
│   └── security.py          # Security utilities, delimiters & input sanitization
├── storage/
│   ├── memory/              # Persistent JSON memory for each advisor
│   └── sessions/            # Deliberation transcripts & session logs
├── tests/
│   ├── test_security.py     # Security test suite (SEC-01 through SEC-06)
│   └── test_slash_commands.py # CLI, slash commands, session & deliberation tests
├── main.py                  # Interactive CLI entrypoint
├── pytest.ini               # Pytest configuration
├── requirements.txt         # Package dependencies
└── README.md                # Documentation
```
