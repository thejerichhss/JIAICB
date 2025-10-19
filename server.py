from flask import Flask, request, jsonify
import os
import json
import requests

app = Flask(__name__)

# Memory store per device (in-memory; for persistence, you can use a JSON file or DB)
MEMORY_FILE = "memory.json"
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r") as f:
        device_memory = json.load(f)
else:
    device_memory = {}

API_KEY = os.environ.get("API_KEY")  # Gemini API key

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def save_memory():
    with open(MEMORY_FILE, "w") as f:
        json.dump(device_memory, f, indent=2)

@app.route("/api", methods=["GET", "POST"])
def api():
    # Get device ID from query or JSON
    device_id = request.args.get("device") or request.json.get("device") if request.is_json else None
    if not device_id:
        return jsonify({"error": "Device ID required"}), 400

    # Clear memory if requested
    if request.args.get("clear") == "true":
        device_memory[device_id] = []
        save_memory()
        return jsonify({"status": "cleared"})

    # View history
    if request.args.get("view") == "history":
        return jsonify(device_memory.get(device_id, []))

    # Handle POST import from front-end
    if request.method == "POST" and request.is_json:
        data = request.json
        if "memory" in data:
            device_memory[device_id] = data["memory"]
            save_memory()
            return jsonify({"status": "memory updated"})

    # Process user input
    user_input = request.args.get("input")
    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    # Build Gemini request payload
    payload = {
        "prompt": {"text": user_input},
        "temperature": 0.7,
        "candidateCount": 1
    }

    try:
        resp = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            params={"key": API_KEY},
            json=payload,
            timeout=20
        )
        resp.raise_for_status()
        reply = resp.json()
        text_reply = reply.get("candidates", [{}])[0].get("content", {}).get("text", "No response.")
    except Exception as e:
        print("Error contacting Gemini:", e)
        text_reply = "Error contacting AI API."

    # Save to memory
    device_memory.setdefault(device_id, []).append({"sender": "You", "text": user_input, "cls": "user"})
    device_memory.setdefault(device_id, []).append({"sender": "AI", "text": text_reply, "cls": "ai"})
    save_memory()

    return text_reply

# Health check
@app.route("/")
def index():
    return "Server is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
