#!/usr/bin/env python3
"""
hackwatch lab -- an intentionally vulnerable web application.

This file is a TARGET, not a product. It exists so the `hackwatch` client has
something legal to attack: your own machine, on your own LAN.

    run:   python3 app.py [port]      # default 8000, binds 0.0.0.0
    stop:  Ctrl-C

Every response carries `X-HackWatch-Lab: 1`. The client refuses to run attack
subcommands against anything that does not identify itself as this lab.

    DO NOT expose this to the internet.
    DO NOT run it on hardware or a network you do not own.

Only the Python standard library is used, so there is nothing to install.
"""

import os
import sqlite3
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(BASE_DIR, "files")
DB_PATH = os.path.join(BASE_DIR, "lab.db")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
HOST = "0.0.0.0"

USERS = [
    ("admin", "hunter2", "admin"),
    ("dev", "trustno1", "developer"),
    ("guest", "guest123", "user"),
    ("jdoe", "summer2024", "user"),
]

TOKENS = [
    (1, "hw_live_9f2c1b7e4d6a8f0c3e5b7d9a1c3e5f7b"),
    (2, "hw_live_2b4d6f8a0c2e4b6d8f0a2c4e6b8d0f2a"),
    (3, "hw_live_7a9c1e3b5d7f9a1c3e5b7d9f1a3c5e7b"),
]

STYLE = """<style>
body{background:#0b0f0a;color:#9fe870;font-family:ui-monospace,Menlo,Consolas,monospace;
     max-width:640px;margin:40px auto;padding:0 16px;line-height:1.5}
h1{font-size:1.4rem;border-bottom:1px solid #274020;padding-bottom:8px}
a{color:#9fe870} .muted{color:#5d7a4e;font-size:.85rem}
input{background:#111a0e;border:1px solid #274020;color:#9fe870;padding:10px;width:100%;box-sizing:border-box;margin:4px 0}
button{margin-top:12px;background:#9fe870;color:#0b0f0a;border:0;padding:10px 18px;font-weight:bold;cursor:pointer}
.box{border:1px solid #274020;padding:14px 16px;margin-top:16px}
</style>"""

LAB_MARKER = '{"app":"hackwatch-lab","version":1,"purpose":"deliberately vulnerable"}\n'

ROBOTS = (
    "User-agent: *\n"
    "Disallow: /admin\n"
    "Disallow: /.env\n"
    "Disallow: /.git/\n"
    "Disallow: /user\n"
)

GIT_CONFIG = (
    "[core]\n"
    "\trepositoryformatversion = 0\n"
    "\tfilemode = true\n"
    "\tbare = false\n"
    "[remote \"origin\"]\n"
    "\turl = https://github.com/0xberkay/hackwatch-lab.git\n"
    "\tfetch = +refs/heads/*:refs/remotes/origin/*\n"
)


def fake_env():
    """Look, a leaked .env. The DB path is real so the lab stays self-consistent."""
    return (
        "# greenvault internal -- dev instance\n"
        "APP_ENV=production\n"
        "APP_DEBUG=false\n"
        "DB_PATH=%s\n"
        "DATABASE_URL=sqlite:///%s\n"
        "SECRET_KEY=dev-secret-do-not-rotate\n"
        "AWS_ACCESS_KEY_ID=lab-placeholder-access-key\n"
        "AWS_SECRET_ACCESS_KEY=lab-placeholder-secret-key\n"
        "STRIPE_SECRET_KEY=lab-placeholder-not-a-real-key\n"
    ) % (DB_PATH, DB_PATH)


def page_head(title):
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>%s</title>%s</head><body>\n"
    ) % (title, STYLE)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT, password TEXT, role TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS tokens ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, token TEXT)"
    )
    if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)", USERS
        )
        cur.executemany(
            "INSERT INTO tokens (user_id, token) VALUES (?, ?)", TOKENS
        )
    conn.commit()
    conn.close()


class LabHandler(BaseHTTPRequestHandler):
    # A fingerprint the app pretends to have. Real server would not say this,
    # but the lab wants something for `hackwatch recon` to find.
    server_version = "Apache/2.4.41 (Debian)"

    def version_string(self):
        return self.server_version

    # ------------------------------------------------------------------ plumbing

    def log_message(self, fmt, *args):
        sys.stderr.write("[lab] %s %s\n" % (self.address_string(), fmt % args))

    def _reply(self, code, body="", ctype="text/html; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-HackWatch-Lab", "1")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if not getattr(self, "_head", False) and body:
            self.wfile.write(body)

    def _redirect(self, location, extra=None):
        headers = {"Location": location}
        headers.update(extra or {})
        self._reply(302, "", extra=headers)

    # ------------------------------------------------------------------- routing

    def do_HEAD(self):
        self._head = True
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        params = parse_qs(parsed.query, keep_blank_values=True)

        if route == "/":
            return self.page_login()
        if route == "/login":
            return self.page_login()
        if route == "/home":
            return self.page_home()
        if route == "/search":
            return self.page_search(params)
        if route == "/user":
            return self.api_user(params)
        if route == "/ping":
            return self.api_ping(params)
        if route == "/download":
            return self.api_download(params)
        if route == "/boom":
            return self.api_boom(params)
        if route == "/admin":
            return self._reply(403, "<h1>403</h1><p>admin only</p>")
        if route == "/robots.txt":
            return self._reply(200, ROBOTS, "text/plain; charset=utf-8")
        if route == "/.env":
            return self._reply(200, fake_env(), "text/plain; charset=utf-8")
        if route == "/.git/config":
            return self._reply(200, GIT_CONFIG, "text/plain; charset=utf-8")
        if route == "/.well-known/hackwatch":
            return self._reply(200, LAB_MARKER, "application/json")
        return self._reply(
            404,
            page_head("404") + "<h1>404</h1><p>not found: %s</p>" % route,
        )

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        params = parse_qs(raw, keep_blank_values=True)

        if parsed.path == "/login":
            return self.api_login(params)
        self._reply(404, "<h1>404</h1><p>no such endpoint</p>")

    # --------------------------------------------------------------------- pages

    def page_login(self):
        if "session=" in self.headers.get("Cookie", ""):
            return self._redirect("/home")
        body = page_head("GreenVault") + (
            "<h1>GreenVault&trade; Customer Portal</h1>"
            "<p class=\"muted\">dev instance &middot; internal use only</p>"
            "<form method=\"post\" action=\"/login\">"
            "<input name=\"username\" placeholder=\"username\" autofocus>"
            "<input name=\"password\" placeholder=\"password\" type=\"password\">"
            "<button type=\"submit\">sign in</button>"
            "</form>"
            "<p class=\"muted\">forgot your password? mail it-support@greenvault.example</p>"
            "</body></html>"
        )
        return self._reply(200, body)

    def page_home(self):
        cookie = self.headers.get("Cookie", "")
        if "session=" not in cookie:
            return self._redirect("/")
        user = cookie.split("session=", 1)[1].split(";", 1)[0]
        body = page_head("Home") + (
            "<h1>Welcome, %s</h1>" % user
        ) + (
            "<div class=\"box\">"
            "<p>account status: <b>active</b></p>"
            "<p class=\"muted\">internal tools: "
            "<a href=\"/ping?host=127.0.0.1\">health check</a> &middot; "
            "<a href=\"/user?id=1\">profile</a></p>"
            "</div>"
            "</body></html>"
        )
        return self._reply(200, body)

    def page_search(self, params):
        query = params.get("q", [""])[0]
        # VULN: reflected XSS -- the query is echoed without escaping.
        body = page_head("Search") + (
            "<h1>Search results for: %s</h1>" % query
        ) + (
            "<div class=\"box\">"
            "<p>no products matched your query.</p>"
            "<form method=\"get\" action=\"/search\">"
            "<input name=\"q\" placeholder=\"search the catalog\">"
            "<button type=\"submit\">search</button>"
            "</form>"
            "</div>"
            "</body></html>"
        )
        return self._reply(200, body)

    # ------------------------------------------------------------------ the vulns

    def api_login(self, params):
        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]
        # VULN: SQL injection -- credentials interpolated straight into the query.
        query = (
            "SELECT id, username, role FROM users "
            "WHERE username = '%s' AND password = '%s'"
        ) % (username, password)
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(query).fetchall()
            conn.close()
        except sqlite3.Error as error:
            self.log_message("sql error: %s", error)
            return self._reply(500, "<h1>500</h1><p>%s</p>" % error)
        if rows:
            _, name, role = rows[0]
            return self._redirect(
                "/home",
                extra={
                    "Set-Cookie": "session=%s; Path=/" % name,
                    "X-Auth": "granted",
                    "X-Role": role,
                },
            )
        return self._reply(401, page_head("Denied")
                           + "<h1>401</h1><p>invalid credentials</p>",
                           extra={"X-Auth": "denied"})

    def api_user(self, params):
        ident = params.get("id", ["1"])[0]
        # VULN: SQL injection -- `id` is used as an integer expression, so
        # `0 UNION SELECT ...` walks the whole table.
        query = (
            "SELECT id, username, password, role FROM users WHERE id = %s" % ident
        )
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(query).fetchall()
            conn.close()
        except sqlite3.Error as error:
            return self._reply(
                500,
                "sql error: %s\nquery: %s\n" % (error, query),
                "text/plain; charset=utf-8",
            )
        if not rows:
            return self._reply(404, "no user\n", "text/plain; charset=utf-8")
        lines = []
        for row in rows:
            lines.append("id=%s user=%s pass=%s role=%s" % row)
        return self._reply(
            200, "\n".join(lines) + "\n", "text/plain; charset=utf-8"
        )

    def api_ping(self, params):
        host = params.get("host", ["127.0.0.1"])[0]
        # VULN: command injection -- `host` is appended to a shell command.
        command = "ping -c 1 -W 2 " + host
        try:
            done = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=10
            )
            return self._reply(
                200, done.stdout + done.stderr, "text/plain; charset=utf-8"
            )
        except subprocess.TimeoutExpired:
            return self._reply(
                504, "ping: timed out\n", "text/plain; charset=utf-8"
            )

    def api_download(self, params):
        name = params.get("file", [""])[0]
        if not name:
            return self._reply(
                400, "usage: /download?file=notes.txt\n", "text/plain; charset=utf-8"
            )
        # VULN: path traversal -- join() happily takes `../../` and absolute paths.
        path = os.path.join(FILES_DIR, name)
        try:
            with open(path, "rb") as handle:
                return self._reply(
                    200, handle.read(), "text/plain; charset=utf-8"
                )
        except OSError as error:
            return self._reply(
                404, "no such file: %s\n" % error, "text/plain; charset=utf-8"
            )

    def api_boom(self, params):
        raw = params.get("mb", ["16"])[0]
        try:
            megabytes = int(raw)
        except ValueError:
            return self._reply(
                400, "mb must be an integer\n", "text/plain; charset=utf-8"
            )
        if megabytes <= 0:
            return self._reply(
                400, "mb must be positive\n", "text/plain; charset=utf-8"
            )
        # VULN: unauthenticated, uncapped memory allocation. Ask for a terabyte
        # and the process dies -- MemoryError if Python is lucky, the OOM killer
        # if it is not.
        try:
            ballast = bytearray(megabytes * 1024 * 1024)
            for offset in range(0, len(ballast), 4096):
                ballast[offset] = 1
        except MemoryError:
            self.log_message("out of memory at %d MB; dying", megabytes)
            sys.stderr.flush()
            os._exit(70)
        return self._reply(
            200, "allocated %d MB\n" % megabytes, "text/plain; charset=utf-8"
        )


def main():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), LabHandler)
    server.daemon_threads = True
    print("hackwatch lab listening on http://%s:%d" % (HOST, PORT), flush=True)
    print("database: %s" % DB_PATH, flush=True)
    print("DO NOT expose this to the internet. Ctrl-C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nlab stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
