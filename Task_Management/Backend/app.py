import os
from pathlib import Path

import mysql.connector
from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "Frontend"

app = Flask(__name__)
CORS(app)

CATEGORIES = {"task", "exam"}
PRIORITIES = {"high", "medium", "low"}

EDITABLE = {
    "title",
    "category",
    "priority",
    "due_date",
    "remind_at",
    "is_done"
}


def get_db_config():
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "root1234"),
        "database": os.getenv("DB_NAME", "taskmanager"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "use_pure": True,
    }

    ssl_ca = os.getenv("DB_SSL_CA")
    if ssl_ca:
        config["ssl_ca"] = ssl_ca
        config["ssl_verify_cert"] = True
    elif os.getenv("DB_SSL_DISABLED", "").lower() in ("true", "1"):
        config["ssl_disabled"] = True

    return config


def run(sql, params=(), fetch=False):
    db_config = get_db_config()
    conn = mysql.connector.connect(**db_config)
    cur = None

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)

        if fetch:
            return cur.fetchall()

        conn.commit()
        return cur.lastrowid

    finally:
        if cur:
            cur.close()
        conn.close()


def clean(row):
    out = {
        k: (v.isoformat() if hasattr(v, "isoformat") else v)
        for k, v in row.items()
    }

    if "is_done" in out:
        out["is_done"] = bool(out["is_done"])

    return out


def norm_dt(value):
    if not value:
        return None

    value = str(value).replace("T", " ")

    if len(value) == 16:
        value += ":00"

    return value


def get_task(task_id):
    rows = run(
        "SELECT * FROM tasks WHERE id = %s",
        (task_id,),
        fetch=True
    )

    return clean(rows[0]) if rows else None


@app.get("/api")
def api_status():
    return jsonify({
        "status": "success",
        "message": "Task Management API is running"
    })


@app.get("/")
def index():
    index_file = FRONTEND_DIR / "index.html"

    if not index_file.exists():
        return jsonify({
            "error": "Frontend index.html not found"
        }), 404

    return send_from_directory(
        str(FRONTEND_DIR),
        "index.html"
    )


@app.get("/<path:filename>")
def serve_frontend(filename):
    file_path = FRONTEND_DIR / filename

    if not file_path.exists():
        abort(404)

    return send_from_directory(
        str(FRONTEND_DIR),
        filename
    )


@app.get("/api/tasks")
def list_tasks():
    rows = run(
        """
        SELECT *
        FROM tasks
        ORDER BY
            is_done,
            due_date IS NULL,
            due_date,
            created_at DESC
        """,
        fetch=True
    )

    return jsonify([clean(row) for row in rows])


@app.post("/api/tasks")
def create_task():
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    category = data.get("category", "task")
    priority = data.get("priority", "medium")

    if not title:
        return jsonify({
            "error": "Title is required"
        }), 400

    if category not in CATEGORIES:
        return jsonify({
            "error": "Invalid category"
        }), 400

    if priority not in PRIORITIES:
        return jsonify({
            "error": "Invalid priority"
        }), 400

    new_id = run(
        """
        INSERT INTO tasks
        (title, category, priority, due_date, remind_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            title,
            category,
            priority,
            data.get("due_date") or None,
            norm_dt(data.get("remind_at"))
        )
    )

    return jsonify(get_task(new_id)), 201


@app.patch("/api/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True) or {}

    sets = []
    vals = []

    for key in EDITABLE & data.keys():
        value = data[key]

        if key == "remind_at":
            value = norm_dt(value)

        elif key == "due_date":
            value = value or None

        elif key == "is_done":
            value = 1 if value else 0

        sets.append(f"{key} = %s")
        vals.append(value)

    if not sets:
        return jsonify({
            "error": "Nothing to update"
        }), 400

    run(
        f"""
        UPDATE tasks
        SET {", ".join(sets)}
        WHERE id = %s
        """,
        (*vals, task_id)
    )

    task = get_task(task_id)

    if not task:
        return jsonify({
            "error": "Task not found"
        }), 404

    return jsonify(task), 200


@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    run(
        "DELETE FROM tasks WHERE id = %s",
        (task_id,)
    )

    return "", 204


@app.errorhandler(mysql.connector.Error)
def handle_db_error(error):
    msg = error.msg if hasattr(error, "msg") else str(error)
    return jsonify({
        "error": f"Database connection error: {msg}. Ensure DB environment variables (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME) are configured."
    }), 500


@app.errorhandler(404)
def page_not_found(error):
    return jsonify({
        "error": "Route not found",
        "path": request.path
    }), 404


@app.errorhandler(Exception)
def handle_generic_error(error):
    return jsonify({
        "error": f"Server error: {str(error)}"
    }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )