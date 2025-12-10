# Project Documentation: AI Hospitality Navigator

**Version**: 1.0.0
**Status**: Stable / Offline-Capable
**Author**: [Your Name/Team]

---

## 1. Executive Summary

**AI Hospitality Navigator** is a cutting-edge, voice-activated assistant designed to revolutionize the dining experience. Unlike traditional digital menus or rigid chatbot systems, this project employs **Generative AI** and **Retrieval Augmented Generation (RAG)** to understand natural language queries, offer personalized recommendations, and process orders with human-like understanding.

The system is architected with a strict **"Offline-First"** philosophy. Recognizing that reliable internet is not always available in hospitality environments, every critical component—from Speech Recognition (STT) to Intelligence (LLM) to Voice Synthesis (TTS)—runs locally on the host machine. This ensures zero downtime, zero API costs, and maximum data privacy.

---

## 2. Key Features & Capabilities

### 🧠 **Local Intelligence (RAG)**
- **Contextual Understanding**: The AI doesn't just match keywords. It understands "I'm allergic to nuts" and actively filters the menu logic to provide safe options.
- **RAG Architecture**: We use `LangChain` to bridge a frozen Large Language Model (Ollama/Qwen) with live, dynamic data (`menu.json`). This allows restaurant owners to update prices or ingredients without retraining the AI.
- **Structured Output**: The AI is prompted to return valid JSON, acting as a translator between messy human speech and structured POS (Point of Sale) data.

### 🗣️ **Conversational Interface**
- **Full Duplex Voice**: Users can speak naturally. The system captures audio, processes it, and responds vocally.
- **Wake-Word Free**: The system uses a "Push-to-Talk" model for privacy and precision, avoiding accidental activations in noisy environments.
- **Multi-Modal**: Users can switch seamlessly between voice and text input.

### ⚡ **Performance & Reliability**
- **Pre-Loaded Models**: All heavy AI models are initialized during the application startup (via FastAPI lifespan events). This shifts the "cold start" latency to the boot time, ensuring that the actual user interaction is instant.
- **Caching**: 
    - **Whisper Model**: Downloaded once, cached forever.
    - **Embeddings**: `all-MiniLM-L6-v2` is cached locally.
    - **Vector Store**: ChromaDB persists its index to disk, so re-indexing is only necessary when the menu changes.

---

## 3. System Architecture Details

The application is split into three distinct layers:

### A. The Presentation Layer (Frontend)
Built with **React 19** and **Vite**, this layer handles user interaction.
- **State Management**: Uses React `useState` to manage conversation history (`messages`), current transaction status (`currentOrder`), and UI states (`isModalOpen`).
- **Audio Handling**:
    - Uses the native browser `MediaRecorder API` to capture microphone input as a Blob.
    - Converts backend base64 audio responses into playable `Audio` objects automatically.
- **Design System**: A custom CSS system (`App.css`) implementing a dark, futuristic aesthetic with glassmorphism effects (`backdrop-filter: blur`), responsive animations (`@keyframes pulse`), and mobile-first layouts.

### B. The Logic Layer (Backend)
Built with **FastAPI** (Python 3.10+), this layer orchestrates the AI workflow.
- **`lifespan` Manager**: A critical architectural choice. Instead of loading AI models when a request comes in (which causes timeouts), we use an async context manager to load `faster-whisper` and `LangChain` pipelines into global memory when the server boots.
- **API Endpoints**: RESTful design for maximum compatibility.
- **WebSocket**: Ready for real-time kitchen display updates (`/ws` endpoint).

### C. The Intelligence Layer (AI Engine)
- **STT Engine**: `faster-whisper` (int8 quantization). We use the "tiny" model for a balance of speed and accuracy suitable for command-like speech.
- **Embedding Engine**: `HuggingFaceEmbeddings`. Converts menu items into dense vector representations.
- **Vector Database**: `Chroma`. Stores these vectors and performs "Similarity Search" (KNN) to find the top 3 menu items relevant to a user's query.
- **LLM**: `Ollama` running `qwen2.5:1.5b`. A 1.5 billion parameter model chosen for its ability to run on consumer hardware (even without a GPU) while maintaining high reasoning capabilities.

---

## 4. API Reference

### `POST /rag-query`
The primary interaction point.
- **Input**:
  ```json
  {
    "text": "Do you have anything spicy?",
    "session_id": "default"
  }
  ```
- **Process**:
  1.  **Retrieve**: Searches ChromaDB for "spicy" items.
  2.  **Generate**: Sends context + user query to Ollama.
  3.  **Synthesize**: Sends AI text response to `pyttsx3`.
- **Output**:
  ```json
  {
    "response_text": "Yes, we have Spicy Chicken Wings...",
    "audio_base64": "UklGRi...",
    "order": null
  }
  ```

### `POST /stt`
Standalone speech-to-text endpoint.
- **Input**: `multipart/form-data` file upload (audio/wav).
- **Process**: Saves temp file -> Whisper Transcribe -> Delete temp file.
- **Output**: `{"text": "Transcribed speech here"}`

### `GET /health`
Liveness probe.
- **Output**: `{"status": "ok", "message": "Backend is running"}`
- **Usage**: Used by the frontend or container orchestrators to verify the backend is ready to accept traffic.

---

## 5. Codebase Deep Dive

### Backend: `ai_engine.py`
This class is the heart of the RAG system.
- **`__init__`**: Initializes the embedding model. Checks if `data/chroma_db` exists. If not, it triggers `_build_vector_store()`.
- **`_build_vector_store`**: 
    - Reads `data/menu.json`.
    - Iterates through categories and items.
    - Creates a rich-text representation of each item (Name + Price + Desc + Allergens).
    - Embeds them into the vector store.
- **`_build_chain`**: Defines the prompt template. We use a strict prompt that forces the LLM to output JSON. We also include a custom `parse_output` function to handle cases where "chatty" models might include markdown code blocks despite being told not to.

### Backend: `api.py` (TTS optimization)
We replaced the online `gTTS` library with `pyttsx3` for offline capabilities.
- **Logic**:
    - Generates a unique `uuid` for a temporary `.wav` file.
    - `engine.save_to_file(text, filename)` renders the audio.
    - We open the file in binary mode (`rb`), read the bytes, and encode them to Base64.
    - Finally, `os.remove(filename)` ensures we don't clog the disk with temporary audio files.

### Frontend: `api.js`
Separates networking logic from UI logic.
- Uses `axios` for HTTP requests.
- Contains the `voiceToText` function which constructs the `FormData` object required for file uploads.

---

## 6. Data Structure (`menu.json`)

The system relies on a strictly formatted JSON file. This allows dynamic menu updates without code changes.

```json
{
    "restaurant_name": "The Future Dinesh",
    "currency": "USD",
    "categories": {
        "Starters": [
            {
                "name": "Spicy Chicken Wings",
                "price": 12.99,
                "desc": "Crispy wings tossed in spicy buffalo sauce",
                "spice": "High",
                "allergens": ["Gluten", "Dairy"]
            }
        ]
    }
}
```
**Scaling Tip**: To add more items, simply append to this array and restart the backend. The `ai_engine` will detect the file and rebuild the vector index automatically.

---

## 7. Future Roadmap & Extensibility

While the prototype is fully functional, here is the roadmap for production readiness:

1.  **Multi-Language Support**:
    - **Implementation**: Update `pyttsx3` to select different voice IDs based on language detection. Update `menu.json` to have localized descriptions.
2.  **Order Management System (OMS)**:
    - **Current**: Orders are displayed in a modal.
    - **Future**: Integration with Stripe/Square for payments and printing to kitchen thermal printers via the `/ws` WebSocket.
3.  **User Personalization**:
    - **Implementation**: Use the `session_id` to store user preferences (e.g., "User likes vegan food") in a lightweight SQLite database, retrieving this history as part of the RAG context.
4.  **Hardware Integration**:
    - Deploying this software onto a Raspberry Pi 5 or NVIDIA Jetson Nano to create a physical "AI Kiosk" application.

---

## 8. Troubleshooting Guide

### Common Issues
1.  **"AI Engine not available"**:
    - **Cause**: The backend failed to initializing Ollama or Whisper.
    - **Fix**: Check terminal logs. Ensure `ollama serve` is running. Ensure you have RAM available (min 4GB).
2.  **Audio is silent**:
    - **Cause**: Browser auto-play policies.
    - **Fix**: Interact with the page (click anywhere) at least once before using voice features. Chrome blocks audio from playing without user gesture.
3.  **Low Accuracy STT**:
    - **Cause**: Poor microphone quality or background noise.
    - **Fix**: Use the "medium" Whisper model (requires editing `api.py`) for better noise cancellation, at the cost of speed.

---

**End of Documentation**
generated by Antigravity AI
