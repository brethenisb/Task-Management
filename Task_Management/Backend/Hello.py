import os
from pathlib import Path

import mysql.connector
from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)  # lets the frontend (another port / file://) call this API

DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Swetha@2006"),
    "database": os.getenv("DB_NAME", "taskmanager"),
}
CATEGORIES = {"task", "exam"}
PRIORITIES = {"high", "medium", "low"}
EDITABLE = {"title", "category", "priority", "due_date", "remind_at", "is_done"}


@app.errorhandler(mysql.connector.Error)
def db_error(err):
    return jsonify(error="Database error: " + str(err)), 500


def run(sql, params=(), fetch=False):
    conn = mysql.connector.connect(**DB)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        if fetch:
            return cur.fetchall()
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def clean(row):
    out = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()}
    out["is_done"] = bool(out["is_done"])
    return out


def norm_dt(value):
    """'2026-10-06T18:30' -> '2026-10-06 18:30:00' (or None)."""
    if not value:
        return None
    value = value.replace("T", " ")
    return value + ":00" if len(value) == 16 else value


def get_task(task_id):
    rows = run("SELECT * FROM tasks WHERE id = %s", (task_id,), fetch=True)
    return clean(rows[0]) if rows else None


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "task.html")


@app.get("/<path:filename>")
def serve_frontend(filename):
    try:
        return send_from_directory(FRONTEND_DIR, filename)
    except FileNotFoundError:
        abort(404)


@app.get("/api/tasks")
def list_tasks():
    rows = run("SELECT * FROM tasks ORDER BY is_done, due_date IS NULL, due_date, created_at DESC", fetch=True)
    return jsonify([clean(r) for r in rows])


@app.post("/api/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    category = data.get("category", "task")
    priority = data.get("priority", "medium")
    if not title:
        return jsonify(error="Title is required"), 400
    if category not in CATEGORIES or priority not in PRIORITIES:
        return jsonify(error="Invalid category or priority"), 400
    new_id = run(
        "INSERT INTO tasks (title, category, priority, due_date, remind_at) VALUES (%s, %s, %s, %s, %s)",
        (title, category, priority, data.get("due_date") or None, norm_dt(data.get("remind_at"))),
    )
    return jsonify(get_task(new_id)), 201


@app.patch("/api/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    sets, vals = [], []
    for key in EDITABLE & data.keys():
        value = data[key]
        if key == "remind_at":
            value = norm_dt(value)
        elif key == "due_date":
            value = value or None
        elif key == "is_done":
            value = 1 if value else 0
        sets.append(f"{key} = %s")  # key comes from the EDITABLE whitelist
        vals.append(value)
    if not sets:
        return jsonify(error="Nothing to update"), 400
    run(f"UPDATE tasks SET {', '.join(sets)} WHERE id = %s", (*vals, task_id))
    task = get_task(task_id)
    return (jsonify(task), 200) if task else (jsonify(error="Task not found"), 404)


@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    run("DELETE FROM tasks WHERE id = %s", (task_id,))
    return "", 204


if __name__ == "__main__":
    app.run(debug=True, port=5000)