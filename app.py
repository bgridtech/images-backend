import os
import base64
import requests
import psycopg2
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Flask setup
app = Flask(__name__)
CORS(app)

# GitHub config
REPO_OWNER = "bgridtech"
REPO_LIST = ["images", "images1", "images2", "images3"]
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # set this as an env var in Vercel

# NeonDB (Postgres) config — as provided
DB_PARAMS = {
    "host": "ep-crimson-pine-a1dwinf0-pooler.ap-southeast-1.aws.neon.tech",
    "dbname": "neondb",
    "user": "neondb_owner",
    "password": os.getenv("NEON_PASS"),
    "sslmode": "require"
}

def get_db_conn():
    return psycopg2.connect(**DB_PARAMS)

def init_db():
    """Ensure tables exist."""
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS save (
                id SERIAL PRIMARY KEY,
                num INTEGER NOT NULL
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS details (
                id SERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                url TEXT NOT NULL,
                uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """)
            # ensure one row in save
            cur.execute("SELECT COUNT(*) FROM save;")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO save (num) VALUES (0);")
        conn.commit()

def get_next_repo_index():
    """Read current num, return index and next_index."""
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT num FROM save LIMIT 1;")
            current = cur.fetchone()[0]
            idx = current % len(REPO_LIST)
            next_idx = (current + 1) % len(REPO_LIST)
            cur.execute("UPDATE save SET num = %s;", (next_idx,))
        conn.commit()
    return idx

def record_detail(filename, url):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO details (filename, url) VALUES (%s, %s);",
                (filename, url)
            )
        conn.commit()

def upload_to_github(repo, filename, data_bytes):
    """Upload to GitHub and return raw URL."""
    path = f"uploads/{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
    url = f"https://api.github.com/repos/{REPO_OWNER}/{repo}/contents/{path}"
    payload = {
        "message": f"Upload {filename}",
        "content": base64.b64encode(data_bytes).decode("utf-8"),
        "branch": "main"
    }
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    resp = requests.put(url, json=payload, headers=headers)
    resp.raise_for_status()
    return f"https://raw.githubusercontent.com/{REPO_OWNER}/{repo}/main/{path}"

@app.route("/")
def index():
    """Render the HTML upload page."""
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_image():
    if "image" not in request.files:
        return jsonify({"error": "No image file sent"}), 400

    file = request.files["image"]
    data = file.read()
    fname = file.filename

    try:
        # init DB/tables on first use
        init_db()

        # pick repo
        idx = get_next_repo_index()
        repo = REPO_LIST[idx]

        # upload
        raw_url = upload_to_github(repo, fname, data)

        # record
        record_detail(fname, raw_url)

        return jsonify({"url": raw_url}), 200

    except requests.HTTPError as e:
        return jsonify({"error": f"GitHub API error: {e.response.json()}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# no app.run() for Vercel
