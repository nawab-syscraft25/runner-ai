# app.py

import os
from flask import Flask, request, jsonify, render_template, send_from_directory


# from agenticai_lotus import  LotusElectronicsBot
# from try_agentic import chat_with_agent

app = Flask(__name__, static_folder="static", template_folder="templates")
# allow all origins; adjust in production as needed

@app.route("/static")
def serve_static(path):
    return send_from_directory("static", path)

@app.route("/", methods=["GET"])
def index():
    # Renders templates/chatbot.html
    return render_template("chat.html")

from runner_chat import chat as chat_with_agent
import json



@app.route("/chat", methods=["POST"])
def chat():
    payload = request.get_json(force=True)
    message = payload.get("message")
    session_id = payload.get("session_id", "default_session")
    if not message:
        return jsonify({"error": "Missing 'message' in request"}), 400

    try:
        ai_reply = chat_with_agent(message, session_id)
        data = json.loads(ai_reply)
        # print(data)
        response = {
            "status": "success",
            "data": data
        }
        return response
    except Exception as e:
        app.logger.exception("Error in chat_with_agent")
        return jsonify({"error": str(e)})



if __name__ == "__main__":
    # Load PORT from env or default to 8000
    port = int(os.environ.get("PORT", 9000))
    app.run(host="0.0.0.0", port=port, debug=True)
