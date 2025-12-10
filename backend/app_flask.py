"""
Simple Flask backend - more stable than FastAPI on Windows
"""
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Health check
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "message": "Backend is running"})

# Simple test endpoint
@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "AI Hospitality Navigator Backend", "version": "1.0"})

# RAG Query endpoint - placeholder
@app.route('/rag-query', methods=['POST'])
def rag_query():
    try:
        data = request.json
        query_text = data.get('text', '')
        
        # Placeholder response
        return jsonify({
            "response_text": f"You asked: {query_text}",
            "audio_base64": "",
            "order": None
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

# Speech-to-text endpoint - placeholder
@app.route('/stt', methods=['POST'])
def speech_to_text():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        return jsonify({"text": "Speech transcription placeholder"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=False, use_reloader=False)
