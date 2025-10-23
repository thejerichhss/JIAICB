from flask import Flask, send_from_directory, request, jsonify
import requests
import os
import json

app = Flask(__name__, static_folder='.')

# ---------- CONFIG ----------
API_KEY = os.environ.get("JTAICB_API_KEY")  # Set this in Render environment
MEMORY_FILE = "/data/memory.json"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# ---------- MEMORY MANAGEMENT ----------
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            print("⚠️ Failed to load memory.json, resetting.")
            return {}
    return {}

def save_memory():
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(app.memory, f)
    except Exception as e:
        print("❌ Error saving memory:", e)

# Load memory once at startup
app.memory = load_memory()
print(f"✅ Loaded memory for {len(app.memory)} devices")

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

    # Handle memory import via POST JSON
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}

        # Import full memory from frontend
        if "memory" in data and isinstance(data["memory"], list):
            app.memory[device_id] = data["memory"]
            save_memory()
            return "Memory imported successfully!", 200

        # Regular chat input via POST
        user_input = data.get("input", "").strip()
    else:
        user_input = request.args.get("input", "").strip()

    # Clear memory
    if clear:
        app.memory[device_id] = []
        save_memory()
        return "Memory cleared!", 200

    # View chat history
    if view == "history":
        return jsonify(app.memory.get(device_id, []))

    # Handle no input
    if not user_input:
        return "No input", 400

    # Add user message
    app.memory.setdefault(device_id, []).append({"sender": "You", "text": user_input})

    # Keep memory from getting huge (optional cap)
    if len(app.memory[device_id]) > 200:
        app.memory[device_id] = app.memory[device_id][-200:]

    # ---------- GEMINI API ----------
    if not API_KEY:
        reply = "Error: Missing Gemini API key."
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

            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                reply = "".join(p.get("text", "") for p in parts).strip() or "No reply"
            else:
                reply = "No reply"

        except Exception as e:
            reply = f"Error contacting Gemini: {e}"

    # Add AI reply to memory
    app.memory[device_id].append({"sender": "AI", "text": reply})
    save_memory()

    return reply, 200

@app.route("/history")
def history_page():
    try:
        if not os.path.exists(MEMORY_FILE):
            return "<p style='color:white'>No memory file found.</p>"

        with open(MEMORY_FILE, "r") as f:
            all_data = json.load(f)

        html_output = """
        <html><head><title>Chat History</title></head>
        <body style='background:#111;color:white;font-family:monospace;padding:10px;'>
        <h2>Chat History</h2><hr>
        """

        # Loop through each device’s chat
        for device, entries in all_data.items():
            html_output += f"<h3 style='color:#9cf'>Device: {device}</h3><hr>"
            for entry in entries:
                sender = entry.get("sender", "Unknown")
                text = entry.get("text", "").replace("\n", "<br>")
                html_output += f"<p><b style='color:#6cf'>{sender}:</b> {text}</p>"
            html_output += "<hr>"

        html_output += "</body></html>"
        return html_output

    except Exception as e:
        return f"<p style='color:red'>Error loading history: {e}</p>"

# ---------- MAIN ----------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Server running on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port)
