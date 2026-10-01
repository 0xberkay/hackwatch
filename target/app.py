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
from urllib.parse import parse_qs, quote, urlparse

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

PRODUCTS = [
    ("🔐", "Vault Starter", "One vault, two devices, zero fuss.", 4.99),
    ("🧰", "Vault Team", "Shared vaults for small teams.", 12.00),
    ("🏦", "Vault Enterprise", "Audit logs, SSO and a sticker.", 49.00),
    ("🔑", "Hardware Key", "A physical key for your vault.", 29.00),
    ("📱", "Mobile Add-on", "Your secrets on the train.", 3.50),
    ("🧊", "Cold Storage", "Air-gapped, sunglasses included.", 99.00),
]

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


# --------------------------------------------------------------------------
# the look
# --------------------------------------------------------------------------

FAVICON = quote(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<rect width="100" height="100" rx="22" fill="#059669"/>'
    '<text x="50" y="68" font-size="52" text-anchor="middle">'
    "&#128274;</text></svg>"
)

CSS = """
:root{--bg:#f4f7f5;--card:#ffffff;--ink:#0f172a;--muted:#64748b;
--brand:#059669;--brand-dark:#047857;--line:#e2e8f0;--danger:#dc2626}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,
"Helvetica Neue",Arial,sans-serif;color:var(--ink);background:var(--bg);
line-height:1.6}
a{color:var(--brand-dark);text-decoration:none}
a:hover{text-decoration:underline}
h1,h2,h3{line-height:1.25;margin:0 0 .5rem}
p{margin:.25rem 0 1rem}
.nav{position:sticky;top:0;z-index:10;display:flex;justify-content:space-between;
align-items:center;padding:12px 24px;background:rgba(255,255,255,.92);
backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.brand{display:flex;gap:10px;align-items:center;font-weight:700;font-size:17px;
color:var(--ink);letter-spacing:-.01em}
.brand:hover{text-decoration:none}
.brand .dot{width:28px;height:28px;border-radius:9px;color:#fff;font-size:15px;
display:grid;place-items:center;
background:linear-gradient(135deg,#10b981,#047857);flex:none}
.nav-links{display:flex;gap:18px;align-items:center;font-size:14px}
.hero{color:#ecfdf5;text-align:center;padding:72px 24px 84px;
background:linear-gradient(165deg,#022c22 0%,#065f46 55%,#047857 100%)}
.hero h1{font-size:clamp(30px,5vw,46px);letter-spacing:-.02em;margin-bottom:12px}
.hero p{max-width:580px;margin:0 auto 28px;color:#a7f3d0;font-size:17px}
.hero .actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.wave{display:block;width:100%;height:48px;margin-bottom:-1px}
.btn{display:inline-block;padding:12px 20px;border-radius:11px;border:0;
font-weight:600;font-size:15px;cursor:pointer;text-decoration:none}
.btn:hover{text-decoration:none;filter:brightness(.95)}
.btn-primary{background:var(--brand);color:#fff}
.btn-ghost{background:rgba(255,255,255,.12);color:#ecfdf5;
border:1px solid rgba(255,255,255,.25)}
.btn-sm{padding:8px 14px;font-size:13px;border-radius:9px}
.section{max-width:980px;margin:0 auto;padding:40px 24px}
.section h2{font-size:24px;letter-spacing:-.01em}
.section .lead{color:var(--muted);margin-bottom:28px}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,
minmax(230px,1fr));margin-top:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:20px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.card h3{font-size:16px;display:flex;gap:8px;align-items:center}
.card .price{color:var(--brand-dark);font-weight:700;margin:6px 0 0}
.card p{color:var(--muted);font-size:14px;margin:6px 0 0}
.tile{width:44px;height:44px;border-radius:12px;display:grid;place-items:center;
font-size:22px;background:linear-gradient(135deg,#d1fae5,#a7f3d0);
margin-bottom:12px}
.auth{max-width:400px;margin:56px auto 72px;padding:0 24px}
.auth .card{padding:30px}
.auth h1{font-size:22px;margin-bottom:4px}
.auth .sub{color:var(--muted);font-size:14px;margin-bottom:20px}
.field{margin:14px 0}
.field label{display:block;font-size:13px;color:var(--muted);
margin-bottom:6px;font-weight:600}
.field input{width:100%;padding:12px 13px;font-size:15px;border:1px solid
var(--line);border-radius:10px;background:#fff;color:var(--ink)}
.field input:focus{outline:2px solid #a7f3d0;border-color:var(--brand)}
.btn-block{width:100%;margin-top:8px}
.alert{border-radius:10px;padding:11px 13px;font-size:14px;margin-bottom:6px}
.alert-error{background:#fef2f2;color:#991b1b;border:1px solid #fecaca}
.dash{max-width:820px;margin:36px auto 72px;padding:0 24px}
.dash-head{display:flex;justify-content:space-between;align-items:center;
gap:12px;flex-wrap:wrap;margin-bottom:24px}
.badge{display:inline-block;background:#d1fae5;color:#065f46;
border-radius:999px;padding:3px 11px;font-size:12px;font-weight:700}
.stats{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,
minmax(160px,1fr));margin-bottom:24px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:16px}
.stat .k{font-size:12px;color:var(--muted);font-weight:600;
text-transform:uppercase;letter-spacing:.04em}
.stat .v{font-size:22px;font-weight:700;margin-top:2px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.empty{text-align:center;color:var(--muted);padding:36px 12px}
.empty .big{font-size:34px;margin-bottom:8px}
.footer{border-top:1px solid var(--line);background:#fff;margin-top:56px;
padding:28px 24px;text-align:center;color:var(--muted);font-size:13px}
.footer a{margin:0 6px}
.center{text-align:center}
"""

BASE_HEAD = (
    "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
    "<title>%s</title>"
    "<link rel=\"icon\" href=\"data:image/svg+xml,%s\">"
    "<style>%s</style></head><body>"
) % ("GreenVault — keep your secrets safe", FAVICON, CSS)

NAV = (
    "<nav class=\"nav\"><a class=\"brand\" href=\"/\">"
    "<span class=\"dot\">&#128274;</span>GreenVault</a>"
    "<div class=\"nav-links\">"
    "<a href=\"/products\">Products</a>"
    "<a href=\"/search\">Search</a>"
    "<a class=\"btn btn-primary btn-sm\" href=\"/login\">Sign in</a>"
    "</div></nav>"
)

FOOTER = (
    "<footer class=\"footer\">&#169; 2026 GreenVault Inc. &middot; "
    "<a href=\"/products\">Products</a> &middot; "
    "<a href=\"/search\">Search</a> &middot; "
    "<a href=\"/login\">Sign in</a><br>"
    "<span class=\"mono\">dev instance &middot; internal use only</span>"
    "</footer></body></html>"
)


def layout(body):
    return BASE_HEAD + NAV + body + FOOTER


def page_landing():
    tiles = "".join(
        "<div class=\"card\"><div class=\"tile\">%s</div>"
        "<h3>%s</h3><p>%s</p></div>"
        % (icon, name, blurb)
        for icon, name, blurb in [
            ("🛡️", "Encrypted at rest", "AES-256, or so the intern said."),
            ("🌍", "Everywhere you are", "Sync that usually keeps up."),
            ("🤝", "Trusted by dozens", "Two of them Fortune 5000."),
        ]
    )
    return layout(
        "<header class=\"hero\">"
        "<h1>Your secrets, kept properly.</h1>"
        "<p>GreenVault stores the things you should not be typing into chat "
        "windows. Bank-grade security, small-business pricing.</p>"
        "<div class=\"actions\">"
        "<a class=\"btn btn-primary\" href=\"/login\">Sign in</a>"
        "<a class=\"btn btn-ghost\" href=\"/products\">Browse products</a>"
        "</div></header>"
        "<svg class=\"wave\" viewBox=\"0 0 1200 48\" preserveAspectRatio=\"none\">"
        "<path d=\"M0,48 C200,0 400,40 600,16 C800,-8 1000,32 1200,8 L1200,48 Z\" "
        "fill=\"#f4f7f5\"/></svg>"
        "<main class=\"section\"><h2>Why GreenVault</h2>"
        "<p class=\"lead\">A place for passwords, keys and the note that says "
        "where the actual keys are.</p>"
        "<div class=\"grid\">%s</div></main>" % tiles
    )


def page_products():
    cards = "".join(
        "<div class=\"card\"><div class=\"tile\">%s</div><h3>%s</h3>"
        "<p>%s</p><p class=\"price\">$%.2f / mo</p></div>" % (icon, name, blurb, price)
        for icon, name, blurb, price in PRODUCTS
    )
    return layout(
        "<main class=\"section\"><h2>Products</h2>"
        "<p class=\"lead\">Pick a plan. Cancel by emailing a person.</p>"
        "<div class=\"grid\">%s</div></main>" % cards
    )


def page_search(query):
    # VULN: reflected XSS -- the query is echoed without escaping.
    needle = query.strip().lower()
    matches = [
        (icon, name, blurb, price)
        for icon, name, blurb, price in PRODUCTS
        if needle and needle in name.lower() or needle and needle in blurb.lower()
    ]
    if matches:
        results = "".join(
            "<div class=\"card\"><div class=\"tile\">%s</div><h3>%s</h3>"
            "<p>%s</p><p class=\"price\">$%.2f / mo</p></div>"
            % (icon, name, blurb, price)
            for icon, name, blurb, price in matches
        )
        body = "<div class=\"grid\">%s</div>" % results
    else:
        body = (
            "<div class=\"empty\"><div class=\"big\">🔍</div>"
            "No products matched your query.</div>"
        )
    return layout(
        "<main class=\"section\"><h2>Search</h2>"
        "<p class=\"lead\">Search results for: <b>%s</b></p>"
        "<form method=\"get\" action=\"/search\" class=\"card\" "
        "style=\"padding:16px;display:flex;gap:10px;flex-wrap:wrap\">"
        "<input name=\"q\" placeholder=\"Search the catalog...\" "
        "value=\"%s\" style=\"flex:1;min-width:200px;padding:11px 13px;"
        "font-size:15px;border:1px solid var(--line);border-radius:10px\">"
        "<button class=\"btn btn-primary\" type=\"submit\">Search</button>"
        "</form>%s</main>" % (query, query, body)
    )


def page_login(error=False):
    message = (
        "<div class=\"alert alert-error\">Invalid username or password.</div>"
        if error
        else ""
    )
    return layout(
        "<main class=\"auth\"><div class=\"card\">"
        "<h1>Sign in</h1>"
        "<p class=\"sub\">Welcome back. Your vault missed you.</p>"
        "%s"
        "<form method=\"post\" action=\"/login\">"
        "<div class=\"field\"><label for=\"username\">Username</label>"
        "<input id=\"username\" name=\"username\" placeholder=\"you@greenvault.example\" "
        "autofocus></div>"
        "<div class=\"field\"><label for=\"password\">Password</label>"
        "<input id=\"password\" name=\"password\" type=\"password\" "
        "placeholder=\"••••••••\"></div>"
        "<button class=\"btn btn-primary btn-block\" type=\"submit\">Sign in</button>"
        "</form>"
        "<p class=\"sub\" style=\"margin-top:18px;margin-bottom:0\">"
        "Forgot your password? Mail <span class=\"mono\">"
        "it-support@greenvault.example</span>.</p>"
        "</div></main>" % message
    )


def page_home(user):
    return layout(
        "<main class=\"dash\">"
        "<div class=\"dash-head\"><div><h1 style=\"font-size:24px\">"
        "Welcome back, %s</h1>"
        "<p style=\"color:var(--muted);margin:0\">Everything looks quiet in "
        "your vaults.</p></div>"
        "<span class=\"badge\">&#9679; active</span></div>"
        "<div class=\"stats\">"
        "<div class=\"stat\"><div class=\"k\">Vaults</div>"
        "<div class=\"v\">3</div></div>"
        "<div class=\"stat\"><div class=\"k\">Secrets</div>"
        "<div class=\"v\">128</div></div>"
        "<div class=\"stat\"><div class=\"k\">Plan</div>"
        "<div class=\"v\">Team</div></div>"
        "</div>"
        "<div class=\"card\"><h3>Internal tools</h3>"
        "<p style=\"margin-bottom:10px\">For staff eyes only:</p>"
        "<p style=\"margin:0\"><a href=\"/ping?host=127.0.0.1\">Health check</a> "
        "&middot; <a href=\"/user?id=1\">Profile API</a> &middot; "
        "<a href=\"/products\">Products</a></p></div>"
        "</main>" % user
    )


def page_forbidden():
    return layout(
        "<main class=\"auth\"><div class=\"card center\">"
        "<h1>403</h1><p class=\"sub\" style=\"margin-bottom:0\">"
        "Admins only. You are clearly not an admin.</p></div></main>"
    )


def page_not_found(path):
    return layout(
        "<main class=\"auth\"><div class=\"card center\">"
        "<h1>404</h1><p class=\"sub\" style=\"margin-bottom:0\">"
        "Nothing lives at <span class=\"mono\">%s</span>.</p></div></main>" % path
    )


def page_error(error):
    return layout(
        "<main class=\"auth\"><div class=\"card\">"
        "<h1>500</h1><p class=\"sub\" style=\"margin-bottom:0\">"
        "Something broke: <span class=\"mono\">%s</span></p></div></main>" % error
    )


# --------------------------------------------------------------------------
# storage
# --------------------------------------------------------------------------


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
            if "session=" in self.headers.get("Cookie", ""):
                return self._redirect("/home")
            return self._reply(200, page_landing())
        if route == "/products":
            return self._reply(200, page_products())
        if route == "/login":
            return self._reply(200, page_login())
        if route == "/home":
            return self.page_home()
        if route == "/search":
            return self._reply(200, page_search(params.get("q", [""])[0]))
        if route == "/user":
            return self.api_user(params)
        if route == "/ping":
            return self.api_ping(params)
        if route == "/download":
            return self.api_download(params)
        if route == "/boom":
            return self.api_boom(params)
        if route == "/admin":
            return self._reply(403, page_forbidden())
        if route == "/robots.txt":
            return self._reply(200, ROBOTS, "text/plain; charset=utf-8")
        if route == "/.env":
            return self._reply(200, fake_env(), "text/plain; charset=utf-8")
        if route == "/.git/config":
            return self._reply(200, GIT_CONFIG, "text/plain; charset=utf-8")
        if route == "/.well-known/hackwatch":
            return self._reply(200, LAB_MARKER, "application/json")
        return self._reply(404, page_not_found(route))

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        params = parse_qs(raw, keep_blank_values=True)

        if parsed.path == "/login":
            return self.api_login(params)
        self._reply(404, page_not_found(parsed.path))

    # --------------------------------------------------------------------- pages

    def page_home(self):
        cookie = self.headers.get("Cookie", "")
        if "session=" not in cookie:
            return self._redirect("/")
        user = cookie.split("session=", 1)[1].split(";", 1)[0]
        return self._reply(200, page_home(user))

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
            return self._reply(500, page_error(error))
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
        return self._reply(401, page_login(error=True), extra={"X-Auth": "denied"})

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
