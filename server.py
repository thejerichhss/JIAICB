from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)
API_KEY = os.getenv("GEMINI_API_KEY")

# Each device has its own conversation memory
memory_store = {}

@app.route("/api", methods=["GET", "POST"])
def chat():
    global memory_store

    # Handle POST (imported chat)
    if request.method == "POST":
        data = request.get_json(force=True)
        memory_store = data.get("memory", {})
        return jsonify({"status": "ok"})

    device_id = request.args.get("device", "unknown")
    clear = request.args.get("clear")
    view = request.args.get("view")
    user_input = request.args.get("input")

    # Clear device memory
    if clear:
        memory_store.pop(device_id, None)
        return "Memory cleared for device."

    # Show memory as HTML (history view)
    if view == "history":
        history = memory_store.get(device_id, [])
        html = "<html><body style='background:#111;color:#eee;font-family:sans-serif;'>"
        html += "<h2>Chat History for Device</h2>"
        for msg in history:
            html += f"<p><b>{msg['sender']}:</b> {msg['text']}</p>"
        html += "</body></html>"
        return html

    # Process normal user input
    if not user_input:
        return "No input provided.", 400

    # Initialize memory for this device
    if device_id not in memory_store:
        memory_store[device_id] = []

    # Add user message
    memory_store[device_id].append({"sender": "You", "text": user_input, "cls": "user"})

    # Prepare Gemini payload
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_input}]
            }
        ]
    }

    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            headers={"Content-Type": "application/json"},
            params={"key": API_KEY},
            json=payload,
            timeout=20
        )
        resp.raise_for_status()
        data = resp.json()
        output_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    except Exception as e:
        output_text = f"Error: {e}"

    # Save AI response
    memory_store[device_id].append({"sender": "AI", "text": output_text, "cls": "ai"})

    return output_text


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
