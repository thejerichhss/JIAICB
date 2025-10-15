from flask import Flask, request, jsonify, send_from_directory
import os, json, requests

app = Flask(__name__)
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# --- API Key (only from environment) ---
API_KEY = os.environ.get("JTAICB_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing environment variable: JTAICB_API_KEY")

@app.route("/api", methods=["GET"])
def handle_request():
    # Use IP as session key (you can replace with user IDs later)
    client_ip = request.remote_addr.replace(".", "_")
    memory_file = os.path.join(DATA_DIR, f"memory_{client_ip}.txt")

    # --- View history ---
    if request.args.get("view") == "history":
        if os.path.exists(memory_file):
            with open(memory_file) as f:
                return f"<pre style='color:white; white-space:pre-wrap;'>{f.read()}</pre>"
        return "(No history found.)"

    # --- Clear memory ---
    if request.args.get("clear") == "true":
        if os.path.exists(memory_file):
            os.remove(memory_file)
        return "Conversation memory cleared!"

    # --- User input ---
    user_prompt = request.args.get("input", "")
    if not user_prompt:
        return "<p>Usage: /api?input=Your+prompt+here</p>"

    # Save user message
    with open(memory_file, "a") as f:
        f.write(f"User: {user_prompt}\n")

    # Build chat context
    context = []
    with open(memory_file) as f:
        for line in f:
            if line.startswith("User:"):
                context.append({"role": "user", "parts": [{"text": line[6:].strip()}]})
            elif line.startswith("AI:"):
                context.append({"role": "model", "parts": [{"text": line[4:].strip()}]})

    # Add current input
    context.append({"role": "user", "parts": [{"text": user_prompt}]})
    payload = {"contents": context}

    # --- Send request to Gemini ---
    resp = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        headers={"Content-Type": "application/json"},
        params={"key": API_KEY},
        json=payload,
        timeout=20
    )

    reply = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    with open(memory_file, "a") as f:
        f.write(f"AI: {reply}\n")

    return reply.replace("\n", "<br>")

@app.route("/")
def serve_index():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>")
def serve_file(path):
    return send_from_directory(".", path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
