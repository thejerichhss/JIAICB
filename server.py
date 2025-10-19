from flask import Flask, send_from_directory, request, jsonify
import requests
import os

app = Flask(__name__, static_folder='.')

API_KEY = os.environ.get("JTAICB_API_KEY")  # Set this in Render environment

# Serve index.html at root
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# Serve other static files (JS, CSS)
@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

# API endpoint for chat
@app.route('/api', methods=['GET', 'POST'])
def api():
    device_id = request.args.get('device', 'unknown')
    clear = request.args.get('clear', 'false').lower() == 'true'
    view = request.args.get('view', None)

    # Memory stored per device
    if not hasattr(app, 'memory'):
        app.memory = {}

    if clear:
        app.memory[device_id] = []
        return "Memory cleared!", 200

    if view == 'history':
        return jsonify(app.memory.get(device_id, []))

    user_input = request.args.get('input', '')
    if not user_input:
        return "No input", 400

    # Add user input to memory
    app.memory.setdefault(device_id, []).append({"sender": "You", "text": user_input})

    # Prepare Gemini API request
    payload = {
        "prompt": user_input,
        "temperature": 0.7,
        "maxOutputTokens": 500
    }

    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            headers={"Content-Type": "application/json"},
            params={"key": API_KEY},
            json=payload,
            timeout=20
        )
        data = resp.json()

        # Parse Gemini response correctly
        candidates = data.get("candidates", [])
        if candidates and "output" in candidates[0]:
            content_list = candidates[0]["output"].get("content", [])
            reply = "".join(c.get("text", "") for c in content_list if c.get("type") == "text")
            if not reply.strip():
                reply = "No reply"
        else:
            reply = "No reply"

    except Exception as e:
        reply = f"Error: {e}"

    # Add AI reply to memory
    app.memory[device_id].append({"sender": "AI", "text": reply})

    return reply, 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
