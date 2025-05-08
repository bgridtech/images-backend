from flask import Flask, request, jsonify, render_template
import base64
import requests
import os
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_image():
    try:
        image = request.files["image"]
        image_data = image.read()
        image_name = image.filename

        GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
        REPO = "yourusername/your-repo"
        BRANCH = "main"
        TIMESTAMP = datetime.now().strftime("%Y%m%d%H%M%S")
        PATH = f"uploads/{TIMESTAMP}_{image_name}"
        COMMIT_MSG = f"Upload {image_name} at {TIMESTAMP}"

        encoded = base64.b64encode(image_data).decode("utf-8")

        url = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "message": COMMIT_MSG,
            "content": encoded,
            "branch": BRANCH
        }

        response = requests.put(url, json=payload, headers=headers)

        if response.status_code in [200, 201]:
            raw_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{PATH}"
            return jsonify({ "url": raw_url }), 200
        else:
            return jsonify({ "error": response.json() }), 500

    except Exception as e:
        return jsonify({ "error": str(e) }), 500

# No app.run() needed for Vercel
