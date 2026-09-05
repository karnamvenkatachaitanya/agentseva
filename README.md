# AgentSeva — Razorpay Agentic Commerce & Recovery Engine

> A **session-aware payments agent** for Indian Kirana stores. Claude drives Razorpay
> commerce actions through **strictly-typed tool calls**, every rupee passes a
> **hard financial guardrail**, every step is written to an **append-only audit trail**,
> and failed payments are automatically salvaged by a **revenue-recovery engine**.

Built for the **Razorpay Agentic Commerce Buildathon**: safe, auditable, autonomous money movement.

---

## ✨ Highlights

- 🤖 **Bounded agent state machine** — Claude 3.5 Sonnet tool-use, capped at **6 steps/turn**, deterministic (`temperature=0`) so it can never loop or hallucinate raw JSON.
- 🛡️ **PaymentGuardrailValidator** — hard caps (₹50,000/order, ₹1,00,000/session), a **circuit breaker** (opens after 3 sequential failures), and **risk-based human-in-the-loop** escalation.
- 🧾 **Append-only audit trail** — every state change and money-moving call writes an immutable `initiated → success/failed` record pair to `transaction_audit_logs`.
- 💸 **Revenue Recovery Engine** — detects `payment.failed` webhooks and dropped checkouts, diagnoses the root cause, and issues a **UPI retry / fresh / discount** payment link.
- 🔒 **Secure gateway** — CORS, rate limiting (slowapi), HMAC-SHA256 webhook verification, structured exception handlers.
- 🖥️ **Live dual-view console** — chat with the agent on the left, watch the audit decision-tree stream in on the right.
- ✅ **96+ unit tests**, and a **mock mode** that runs the entire system offline with no API keys.

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph Client["🖥️ Frontend · React + Vite (nginx)"]
        Chat["Agent Chat (left)"]
        Audit["Live Audit Log (right)"]
    end

    subgraph Gateway["⚡ FastAPI Gateway · app/main.py"]
        direction TB
        MW["CORS · slowapi rate limit · structured error handlers"]
        EP1["POST /api/v1/agent/chat"]
        EP2["POST /api/v1/webhooks/razorpay"]
        EP3["GET /api/v1/health"]
        EP4["GET /api/v1/metrics"]
        EP5["GET /api/v1/audit/traces/{session_id}"]
    end

    subgraph Core["🧠 Agent Core · app/agent"]
        SM["CommerceAgentCore<br/>bounded 6-step state machine"]
        GR["PaymentGuardrailValidator<br/>caps · circuit breaker · risk score"]
        REC["RevenueRecoveryEngine<br/>diagnose → intervene"]
    end

    subgraph Tools["🔧 Tool Registry · app/tools"]
        RZ["Razorpay tools (Pydantic v2)<br/>order · link · verify · recover"]
    end

    subgraph Ext["🌐 Razorpay"]
        API["Razorpay REST API<br/>(live) / mock simulator"]
    end

    subgraph Data["🗄️ Audit Store"]
        DB[("SQLite / PostgreSQL<br/>transaction_audit_logs")]
    end

    LLM["Claude 3.5 Sonnet<br/>(Anthropic tool-use)"]

    Chat -->|message + session_id| EP1
    Audit -->|poll 2s| EP5
    EP1 --> SM
    SM <-->|tool schemas + results| LLM
    SM -->|validate money moves| GR
    SM --> RZ
    EP2 --> REC
    REC --> GR
    REC --> RZ
    RZ --> API
    SM -->|before/after| DB
    REC -->|before/after| DB
    EP5 --> DB
    EP4 --> DB
```

**Request lifecycle (chat):** user message → gateway → `CommerceAgentCore` asks Claude
→ Claude proposes a tool call → **guardrail validates the amount** → tool executes against
Razorpay (or mock) → result audited (before/after) and fed back to Claude → repeat until
done or the 6-step ceiling → `AgentResponse(reply, actions_taken, is_complete, requires_escalation)`.

---

## 🏆 How it solves the Razorpay Buildathon requirements

| Buildathon theme | How AgentSeva delivers it |
|---|---|
| **Agentic commerce** | An LLM agent autonomously creates orders, issues payment links, verifies and refunds payments — all via Razorpay tool calls, not hard-coded flows. |
| **Financial safety** | `PaymentGuardrailValidator` gates *every* monetary action: per-order & per-session caps, positive-integer paise checks, currency allowlist, and a circuit breaker that halts repeated failures. |
| **Trust & auditability** | An **append-only** `transaction_audit_logs` table records intent, reasoning, payload, API response, status and latency — before and after each external call. `GET /audit/traces/{session_id}` replays the full decision tree for evaluators. |
| **Revenue recovery** | Automatically turns `payment.failed` webhooks and abandoned checkouts into recovered revenue via diagnosed, compliant interventions (UPI retry / fresh link / capped discount). |
| **No hallucinations** | Rigid Pydantic v2 tool schemas + `temperature=0` + deterministic stopping conditions; invalid tool arguments are rejected before any money moves. |
| **Human-in-the-loop** | Transactions whose risk score exceeds threshold return `requires_escalation=true` and are held for confirmation instead of executing. |
| **Production readiness** | Dockerized gateway with CORS, rate limiting, HMAC-verified webhooks, health & metrics endpoints, and a one-command `docker-compose` boot. |

---

## 🚀 Quickstart (3 steps)

> Prerequisites: **Docker** + **Docker Compose**. No API keys needed — it runs in **mock mode** out of the box.

```bash
# 1) Clone
git clone <your-repo-url> agentseva && cd agentseva

# 2) (optional) add real keys — copy the template and fill in what you have
cp .env.example .env      # set ANTHROPIC_API_KEY / RAZORPAY_* to go live; skip to stay in mock mode

# 3) Boot the whole stack
docker-compose up --build
```

Then open:

| URL | What |
|---|---|
| **http://localhost:5173** | Dual-view console — chat left, live audit logs right |
| **http://localhost:8000/docs** | Interactive API docs (Swagger) |
| **http://localhost:8000/api/v1/health** | Health + dependency status |
| **http://localhost:8000/api/v1/metrics** | Transactions processed · money recovered · failure rate |

**Try it without any keys:** in the console, click **“Simulate failed payment”** or
**“Simulate dropped checkout”** — the Revenue Recovery Engine issues a mock Razorpay
payment link and the audit trail streams in on the right. Add an `ANTHROPIC_API_KEY`
to enable the live chat agent.

---

## 🔌 API surface

| Method & path | Purpose |
|---|---|
| `POST /api/v1/agent/chat` | Session-aware agent interaction → `AgentResponse` |
| `POST /api/v1/webhooks/razorpay` | HMAC-verified webhook receiver (drives recovery) |
| `GET  /api/v1/health` | Liveness + dependency status |
| `GET  /api/v1/metrics` | Transactions processed, money recovered, failure rate |
| `GET  /api/v1/audit/traces/{session_id}` | Full step-by-step decision tree |
| `POST /api/v1/recovery/checkout` | Recover a dropped checkout |
| `POST /api/v1/engine/agent/run` | Lower-level paise-based engine agent |

---

## 🧱 Project structure

```
.
├── Dockerfile                     # backend image (build context = repo root)
├── docker-compose.yml             # backend + frontend
├── .env.example
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py                # ⚡ production gateway (this file)
│       ├── core/                  # config, rate limiting
│       ├── agent/                 # core.py (state machine), guardrails.py, recovery.py
│       ├── tools/razorpay_tools.py# bounded Pydantic v2 tool registry
│       ├── engine/                # paise engine (schemas, guardrails, client, tools, agent)
│       ├── audit/logger.py        # append-only transaction_audit_logs
│       ├── db/base.py             # SQLAlchemy engine/session
│       └── api/v1/                # routers (ai, engine, audit, recovery)
└── frontend/
    ├── Dockerfile · nginx.conf
    └── src/pages/AgentConsole.tsx # live dual-view
```

---

## ⚙️ Configuration

All settings come from environment variables / `.env` (see `.env.example`). Key ones:

| Variable | Default | Meaning |
|---|---|---|
| `RAZORPAY_MODE` | `mock` | `mock` (offline simulator) or `live` |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | — | Razorpay credentials for live mode |
| `RAZORPAY_WEBHOOK_SECRET` | — | Enables HMAC-SHA256 webhook verification |
| `ANTHROPIC_API_KEY` | — | Enables the live Claude chat agent |
| `CLAUDE_MODEL` | `claude-3-5-sonnet-latest` | Agent model |
| `MAX_TXN_AMOUNT_PAISE` | `5000000` | Per-order cap (₹50,000) |
| `DAILY_CAP_PAISE` | `20000000` | Daily/session ceiling |

---

## 🧪 Testing

```bash
cd backend
pip install -r requirements.txt
pytest            # 96+ tests, fully offline (mock mode)
```

Covers guardrails, circuit breaker, audit before/after semantics, recovery diagnosis
& interventions, the bounded state machine, the Razorpay tool registry, and the gateway
endpoints (via `TestClient`).

---

## 🔐 Security notes

- Webhooks are verified with **HMAC-SHA256** (`X-Razorpay-Signature`) via constant-time comparison when `RAZORPAY_WEBHOOK_SECRET` is set; invalid signatures get `401`.
- The audit trail is **append-only by construction** — no update/delete path is exposed.
- Rate limiting (slowapi) protects the chat and webhook endpoints; secrets are never committed (`.env` is git-ignored; `.env.example` documents them).
