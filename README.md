# 🏛️ Board of Advisors: Autonomous Multi-Agent Decision Council

An autonomous executive advisory board designed to help founders, leaders, and decision-makers navigate high-stakes strategic, financial, technical, and governance dilemmas.

Powered by **Gemini 3.8 Flash** with **medium reasoning effort**, orchestrated using **Antigravity CLI (`agy`)** in detached mode.

---

## 🌟 Key Features

1. **Dynamic, Problem-Tailored Board Assembly**:
   - Rather than static predefined roles, the orchestrator analyzes your specific problem and dynamically convenes a bespoke board of **at most 10 specialist advisors** (typically 4–6) with complementary expertise, distinct personas, and opposing viewpoints tailored to the dilemma.
   - Each advisor is endowed with a realistic bio, specific cognitive biases, core beliefs, and an assigned `@tag` (e.g. `@Elena`, `@Marcus`, `@Victoria`, `@Tariq`).

2. **Adaptive Deliberation with a 3-Round Ceiling**:
   - **No Fixed Round Count**: Deliberation adapts to the complexity of the dilemma (at most 3 rounds).
   - **Round 1 (Opening Assessments)**: Each advisor presents their domain perspective and poses sharp, direct questions to colleagues via `@mentions`.
   - **Round 2 (Cross-Examination)**: Advisors answer directed questions, stress-test peer assumptions, and navigate trade-offs. If consensus is reached early, the board can proceed directly to action plan synthesis.
   - **Round 3 (Mandatory Conclusion)**: If deliberation reaches the third round, advisors receive a strict mandate: *this is the final round and they must come to a definitive conclusion*. They resolve remaining disagreements and deliver their final verdicts.

3. **Autonomous Tagging & Dynamic Routing**:
   - Advisors dynamically tag other advisors with `@tags` to challenge them directly.
   - The orchestrator extracts mentions, routes directed inquiries, and gives priority speaking turns to tagged advisors so questions are answered head-on.

4. **Per-Advisor Persistent Memory**:
   - Each advisor maintains private long-term memory stored under `storage/memory/<advisor_id>.json`.
   - Remembers past stances, problem contexts, and impressions of fellow board members across sessions.

5. **Antigravity CLI Detached Execution**:
   - Every LLM agent turn is invoked via the `agy` CLI using `--print` in detached, non-blocking mode (`stdin=subprocess.DEVNULL`, Windows no-window process creation).
   - Configured with `gemini-3.8-flash-medium` and `--effort medium`.

6. **Consolidated Plan of Action & Follow-Up**:
   - Synthesizes the debate into an executive decision, immediate 2-week actions, 30/60/90-day validation gates, risk mitigations, and closing verdicts.
   - Interactive chat loop allows you to ask follow-up questions, tag individual advisors, or convene a new bespoke council with `/new`.

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

Dependencies (`rich`, `pyyaml`) are already installed into `.venv`. To reinstall or update:
```powershell
uv pip install -r requirements.txt --python .\.venv\Scripts\python.exe
```

### 2. Run the Board of Advisors
Launch the interactive terminal council:

```powershell
.\.venv\Scripts\python.exe main.py
```

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
├── .venv/                   # Project Python virtual environment
├── config/
│   └── advisors.yaml        # Fallback advisor profiles
├── board/
│   ├── config.py            # CLI paths, model settings & directory constants
│   ├── invoker.py           # Detached Antigravity CLI (agy) runner
│   ├── memory.py            # Per-advisor persistent memory store
│   ├── advisor.py           # Advisor agent logic & round prompt construction
│   ├── advisor_builder.py   # Dynamic advisor JSON parser & sanitizer
│   ├── orchestrator.py      # Dynamic assembly, debate routing & synthesis
│   └── cli_ui.py            # Rich terminal chat panels, badges & formatting
├── storage/
│   ├── memory/              # Persistent JSON memory for each advisor
│   └── sessions/            # Deliberation transcripts & session logs
├── main.py                  # Interactive CLI entrypoint
├── requirements.txt         # Package dependencies
└── README.md                # Documentation
```
