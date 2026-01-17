"""
Vulnerable Flask Application - Test Fixture for Taint Analysis

This module contains INTENTIONALLY VULNERABLE code for testing
KnowGraph's security analysis capabilities. DO NOT use in production!

Vulnerabilities included:
- SQL Injection (CWE-89)
- Cross-Site Scripting (CWE-79)
- Command Injection (CWE-78)
- Path Traversal (CWE-22)
"""

import os
import sqlite3
import subprocess

from flask import Flask, render_template_string, request

app = Flask(__name__)


# ============================================================================
# VULNERABILITY 1: SQL Injection (Critical)
# ============================================================================

@app.route("/login", methods=["POST"])
def vulnerable_login():
    """
    SQL Injection vulnerability - User input directly in query.
    
    Taint flow:
    Source: request.form['username']
    Sink: cursor.execute()
    """
    username = request.form["username"]  # SOURCE: User input
    password = request.form["password"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # VULNERABLE: String concatenation in SQL
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor.execute(query)  # SINK: SQL execution

    result = cursor.fetchone()
    return str(result)


@app.route("/search", methods=["GET"])
def vulnerable_search():
    """
    Another SQL injection via GET parameter.
    
    Taint flow:
    Source: request.args.get('q')
    Sink: cursor.execute()
    """
    search_query = request.args.get("q")  # SOURCE

    conn = sqlite3.connect("products.db")
    cursor = conn.cursor()

    # VULNERABLE: Using .format() with user input
    sql = f"SELECT * FROM products WHERE name LIKE '%{search_query}%'"
    cursor.execute(sql)  # SINK

    return str(cursor.fetchall())


# ============================================================================
# VULNERABILITY 2: Cross-Site Scripting (High)
# ============================================================================

@app.route("/greet", methods=["GET"])
def vulnerable_xss():
    """
    XSS vulnerability - User input rendered without escaping.
    
    Taint flow:
    Source: request.args.get('name')
    Sink: render_template_string()
    """
    name = request.args.get("name", "Guest")  # SOURCE

    # VULNERABLE: render_template_string without escaping
    template = f"<h1>Hello, {name}!</h1>"
    return render_template_string(template)  # SINK


@app.route("/comment", methods=["POST"])
def vulnerable_comment():
    """
    Stored XSS - User comment rendered unsafely.
    
    Taint flow:
    Source: request.form['comment']
    Intermediate: save_comment()
    Sink: render in HTML
    """
    comment = request.form["comment"]  # SOURCE

    # Save to database (intermediate step)
    save_comment(comment)

    # VULNERABLE: Direct HTML rendering
    html = f"<div class='comment'>{comment}</div>"
    return html  # SINK


def save_comment(text):
    """Intermediate function - data flows through here."""
    conn = sqlite3.connect("comments.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO comments VALUES (?)", (text,))
    conn.commit()


# ============================================================================
# VULNERABILITY 3: Command Injection (Critical)
# ============================================================================

@app.route("/ping", methods=["GET"])
def vulnerable_ping():
    """
    Command injection via subprocess.
    
    Taint flow:
    Source: request.args.get('host')
    Sink: subprocess.call()
    """
    host = request.args.get("host", "localhost")  # SOURCE

    # VULNERABLE: User input in shell command
    command = f"ping -c 4 {host}"
    result = subprocess.call(command, shell=True)  # SINK

    return f"Ping result: {result}"


@app.route("/backup", methods=["POST"])
def vulnerable_backup():
    """
    Command injection via os.system.
    
    Taint flow:
    Source: request.form['filename']
    Sink: os.system()
    """
    filename = request.form["filename"]  # SOURCE

    # VULNERABLE: os.system with user input
    cmd = f"tar -czf {filename}.tar.gz /data/{filename}"
    os.system(cmd)  # SINK

    return "Backup created"


# ============================================================================
# VULNERABILITY 4: Path Traversal (Medium)
# ============================================================================

@app.route("/download", methods=["GET"])
def vulnerable_download():
    """
    Path traversal - User can access arbitrary files.
    
    Taint flow:
    Source: request.args.get('file')
    Sink: open()
    """
    filename = request.args.get("file")  # SOURCE

    # VULNERABLE: No path validation
    filepath = f"/var/www/uploads/{filename}"

    with open(filepath) as f:  # SINK
        content = f.read()

    return content


# ============================================================================
# SAFE EXAMPLES (For comparison)
# ============================================================================

@app.route("/safe_login", methods=["POST"])
def safe_login():
    """
    SAFE: Uses parameterized queries.
    
    No taint flow - proper sanitization.
    """
    username = request.form["username"]
    password = request.form["password"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # SAFE: Parameterized query
    cursor.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password)
    )

    result = cursor.fetchone()
    return str(result)


@app.route("/safe_greet", methods=["GET"])
def safe_greet():
    """
    SAFE: Uses Jinja2 auto-escaping.
    
    No taint flow - template engine handles escaping.
    """
    name = request.args.get("name", "Guest")

    # SAFE: Jinja2 escapes by default
    return render_template("greet.html", name=name)


if __name__ == "__main__":
    app.run(debug=True)
