# 🏛️ Board of Advisors: Autonomous Multi-Agent Decision Council

An autonomous executive advisory board designed to help founders, leaders, and decision-makers navigate high-stakes strategic, financial, technical, and governance dilemmas.

Powered by **Gemini 3.8 Flash** with **medium reasoning effort**, orchestrated using **Antigravity CLI (`agy`)** in detached mode.

---

## 🌟 Key Features

1. **Diverse Expert Personas**:
   - **Elena Vance (`@Elena`)** — *Chief Strategy & Market Growth Officer*: Bold, customer-obsessed, focused on distribution, product-market fit, and iteration velocity.
   - **Marcus Sterling (`@Marcus`)** — *Chief Financial & Risk Officer*: Skeptical, numbers-driven, focuses on runway, unit economics, and downside protections.
   - **Dr. Aris Thorne (`@Aris`)** — *Chief Technology & AI Systems Architect*: Pragmatic technologist, scrutinizes architecture, technical debt, and AI leverage.
   - **Maya Lin (`@Maya`)** — *Chief Governance, People & Legal Counsel*: Protects team morale, compliance, reputation, IP, and stakeholder trust.

2. **Per-Advisor Persistent Memory**:
   - Each advisor maintains their own private memory store (stored in `storage/memory/<advisor_id>.json`).
   - Advisors remember their core principles, past stances taken on previous dilemmas, and evolving impressions of their peer board members.

3. **Autonomous Tagging & Targeted Routing**:
   - During deliberations, advisors dynamically tag colleagues (e.g., `@Marcus how does this impact our 12-month runway?` or `@Aris is this feasible without hiring 5 engineers?`).
   - The orchestrator parses `@mentions`, extracts directed questions, and routes priority speaking turns to tagged advisors so they directly address the inquiry.

4. **Multi-Stage Chat-Type Orchestration**:
   - **Phase 1: Opening Perspectives**: Advisors evaluate the user's dilemma from their distinct functional domains.
   - **Phase 2: Round-Table Debate**: Cross-examination where advisors challenge assumptions, resolve disagreements, and build consensus.
   - **Phase 3: Consolidated Action Plan**: An executive synthesis detailing strategic stance, immediate next steps (Weeks 1-2), 30/60/90-day milestones, risk mitigation matrices, and closing verdicts.
   - **Phase 4: Interactive Follow-Up Chat**: The user can ask follow-up questions, tag individual advisors for deeper dives, or present new dilemmas.

5. **Antigravity CLI Detached Execution**:
   - Every LLM agent turn is invoked via the `agy` CLI using `--print` in detached non-blocking mode.
   - Configured with `gemini-3.8-flash-medium` and `--effort medium`.

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

## 💬 Example Deliberation Flow

1. **You enter a dilemma:**
   > *"Should I pivot our B2B document search SaaS to an autonomous customer support agent platform?"*

2. **Initial Assessments:**
   - **Elena (`@Elena`)** analyzes customer willingness to pay and asks: *"@Aris, can we deliver 95%+ accuracy without hallucinations killing our brand?"*
   - **Marcus (`@Marcus`)** breaks down CAC/LTV and asks: *"@Elena, what is the customer churn risk during the transition?"*
   - **Aris (`@Aris`)** evaluates LLM latency, eval pipelines, and API costs.
   - **Maya (`@Maya`)** flags liability, PII handling, and SLA commitments.

3. **Discussion & Cross-Examination:**
   - Advisors directly answer tags addressed to them, sharpen trade-offs, and reach alignment.

4. **Consolidated Plan of Action:**
   - A structured roadmap with immediate next steps, kill-switch milestones, and risk mitigations.

5. **Follow-Up:**
   - You can chat back: *"@Marcus what if we raise a $500k bridge round first?"*

---

## 🛠️ Configuration & Customization

You can add, edit, or remove board members by modifying `config/advisors.yaml`:

```yaml
advisors:
  - id: custom_advisor
    name: "Alex Rivera"
    tag: "@Alex"
    role: "VP of Product Marketing"
    avatar: "🚀"
    color: "bright_cyan"
    persona: "..."
    core_beliefs:
      - "Positioning is everything."
```

---

## 📂 Project Structure

```
board-of-advisors/
├── .venv/                   # Project Python virtual environment
├── config/
│   └── advisors.yaml        # Board member profiles, personas & beliefs
├── board/
│   ├── config.py            # CLI paths, models, and system constants
│   ├── invoker.py           # Detached Antigravity CLI (agy) runner
│   ├── memory.py            # Per-advisor persistent memory store
│   ├── advisor.py           # Advisor agent logic & prompt construction
│   ├── orchestrator.py      # Multi-agent debate, tag routing & synthesis
│   └── cli_ui.py            # Rich terminal formatting & message panels
├── storage/
│   ├── memory/              # Persistent JSON memory for each advisor
│   └── sessions/            # Deliberation transcripts & session logs
├── main.py                  # Interactive CLI entrypoint
├── requirements.txt         # Package dependencies
└── README.md                # Documentation
```

---

## 🔄 Roadmap & Future Iterations

- [ ] **Web UI**: Streamlit or React-based interactive board room with real-time audio or streaming tokens.
- [ ] **Document Ingestion**: Upload pitch decks, financials, or architecture diagrams for advisors to review.
- [ ] **Voting & Formal Governance**: Structured voting rounds (Approve / Reject / Abstain) with minority dissenting opinions formally recorded.
- [ ] **Dynamic Advisor Spawning**: Bring in guest domain specialists (e.g. `@BioTechExpert`, `@CryptoLegal`) on demand for specific problems.
