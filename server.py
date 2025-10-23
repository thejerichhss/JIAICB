from flask import Flask, send_from_directory, request, jsonify
import requests
import os
import json

app = Flask(__name__, static_folder='.')

# ---------- CONFIG ----------
API_KEY = os.environ.get("JTAICB_API_KEY")  # Set this in Render environment
MEMORY_FILE = "memory.json"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# ---------- MEMORY MANAGEMENT ----------
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_memory():
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(app.memory, f)
    except Exception as e:
        print("Error saving memory:", e)

@app.before_first_request
def startup():
    app.memory = load_memory()
    print("✅ Memory loaded:", len(app.memory), "devices")

@app.teardown_appcontext
def shutdown(exception=None):
    save_memory()
    print("💾 Memory saved.")

# ---------- ROUTES ----------
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

@app.route('/api', methods=['GET', 'POST'])
def api():
    device_id = request.args.get('device', 'unknown')
    clear = request.args.get('clear', 'false').lower() == 'true'
    view = request.args.get('view', None)

    if not hasattr(app, 'memory'):
        app.memory = {}

    # Handle memory import via POST JSON
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}

        # Import full memory from frontend
        if "memory" in data and isinstance(data["memory"], list):
            app.memory[device_id] = data["memory"]
            save_memory()
            return "Memory imported successfully!", 200

        # Regular chat input (POST body)
        user_input = data.get("input", "").strip()
    else:
        user_input = request.args.get("input", "").strip()

    # Handle clear memory
    if clear:
        app.memory[device_id] = []
        save_memory()
        return "Memory cleared!", 200

    # View chat history
    if view == "history":
        return jsonify(app.memory.get(device_id, []))

    if not user_input:
        return "No input", 400

    # Add user message
    app.memory.setdefault(device_id, []).append({"sender": "You", "text": user_input})

    # ---------- GEMINI API ----------
    if not API_KEY:
        reply = "Error: Missing API key."
    else:
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": user_input}]}
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500
            }
        }

        try:
            resp = requests.post(
                GEMINI_URL,
                headers={"Content-Type": "application/json"},
                params={"key": API_KEY},
                json=payload,
                timeout=25
            )
            data = resp.json()

            # Parse Gemini reply
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                reply = "".join(p.get("text", "") for p in parts)
                reply = reply.strip() or "No reply"
            else:
                reply = "No reply"

        except Exception as e:
            reply = f"Error contacting Gemini: {e}"

    # Add AI reply to memory
    app.memory[device_id].append({"sender": "AI", "text": reply})
    save_memory()

    return reply, 200

# ---------- MAIN ----------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
