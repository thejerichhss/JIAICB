from flask import Flask, request, send_from_directory, jsonify
import os, requests

app = Flask(__name__)
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
API_KEY = os.environ.get("JTAICB_API_KEY", "MISSING_API_KEY")

def get_ip(req):
    forwarded_for = req.headers.get("X-Forwarded-For", "")
    client_ip = forwarded_for.split(",")[0] if forwarded_for else req.remote_addr
    return client_ip.replace(".", "_").replace(":", "_")

@app.route("/api", methods=["GET", "POST"])
def handle_request():
    ip = get_ip(request)
    memory_file = os.path.join(DATA_DIR, f"memory_{ip}.txt")

    # ✅ POST — handle memory replacement (chat import)
    if request.method == "POST":
        data = request.get_json()
        if not data or "memory" not in data:
            return jsonify({"error": "Invalid request"}), 400
        
        # Replace memory with imported chat
        new_memory = data["memory"]
        with open(memory_file, "w") as f:
            for msg in new_memory:
                sender = msg.get("sender", "System")
                text = msg.get("text", "")
                f.write(f"{sender}: {text}\n")

        return "Memory updated"

    # ✅ GET — handle normal AI messages and history view
    if request.args.get("view") == "history":
        if os.path.exists(memory_file):
            with open(memory_file) as f:
                return f"<pre style='color:white; white-space:pre-wrap;'>{f.read()}</pre>"
        return f"(No history found for this device: {ip})"

    if request.args.get("clear") == "true":
        if os.path.exists(memory_file):
            os.remove(memory_file)
        return f"Memory cleared for device {ip}!"

    user_prompt = request.args.get("input", "")
    if not user_prompt:
        return "<p>Usage: /api?input=Your+prompt+here</p>"

    # Append user message to memory
    with open(memory_file, "a") as f:
        f.write(f"User: {user_prompt}\n")

    # Rebuild context from file
    context = []
    if os.path.exists(memory_file):
        with open(memory_file) as f:
            for line in f:
                if line.startswith("User:"):
                    context.append({"role": "user", "parts": [{"text": line[6:].strip()}]})
                elif line.startswith("AI:"):
                    context.append({"role": "model", "parts": [{"text": line[4:].strip()}]})
    context.append({"role": "user", "parts": [{"text": user_prompt}]})

    payload = {"contents": context}

    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            headers={"Content-Type": "application/json"},
            params={"key": API_KEY},
            json=payload,
            timeout=20
        )
        reply = (
            resp.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
    except Exception as e:
        reply = f"(Error contacting API: {e})"

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
    app.run(host="0.0.0.0", port=10000)
