# How to Run the Project (Universal Guide)

This project is designed to run on **Windows, macOS, and Linux**.

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+** & npm
- **Ollama** (Required for AI Brain) - [Download Here](https://ollama.ai)

### 2. One-Time Setup

**Step A: AI Model (Ollama)**
Open a terminal and run:
```bash
ollama pull qwen2.5:1.5b
```

**Step B: Backend Setup**
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

# Mac / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Step C: Frontend Setup**
```bash
cd frontend
npm install
cd ..
```

---

## 🏃 Running the Project

You need two terminals running simultaneously.

**Terminal 1: Backend**
```bash
# Windows
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Mac / Linux
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2: Frontend**
```bash
cd frontend
npm run dev
```

Then open your browser to **http://localhost:5173** (or the port shown in your terminal).

---

## 🌍 Offline Capability
This project is **fully offline-capable** after the first run.
- **Voice (TTS)**: Uses your system's built-in voice (Zero latency, Offline).
- **AI Brain**: Runs locally via Ollama.
- **Hearing (STT)**: Uses local Whisper model (Cached after first download).

---

## 🛠 Troubleshooting

**Backend won't start?**
- Windows: Ensure you enabled script execution (`Set-ExecutionPolicy RemoteSigned`).
- All: Check if Ollama is running (`ollama serve`).

**"AI Engine not available"?**
- Make sure you ran `ollama pull qwen2.5:1.5b`.
- Check backend logs for errors.

**Frontend connection error?**
- Verify Backend is running on port 8000.
