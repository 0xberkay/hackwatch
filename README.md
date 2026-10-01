# hackwatch

> **Lab only.** `hackwatch` attacks a deliberately vulnerable web application
> that *you* run, on *your* machine. Never point it at a system you do not own
> or have written permission to test. See [Ethics](#ethics).

A wrist-borne web attack tool. `hackwatch` is a POSIX shell script that talks
to a small, intentionally broken web app with nothing but `curl` — and on a
Wear OS watch running [Wear Term](https://github.com/0xberkay/WearTerm) it
buzzes the wrist, posts notifications and speaks while it works.

The whole point is the demo: **take a website down from your smartwatch with a
single command.**

```
$ hackwatch nuke --yes

#   #   #    #### #   # #   #   #   #####  #### #   #
##### ##### #     ###   # # # #####   #   #     #####
...
::reading /.env for the database path
  DB_PATH = /home/you/hackwatch/target/lab.db

  firing in 3...
  firing in 2...
  firing in 1...

#####   #   ####   #### ##### #####       ####   ###  #   # #   #
  #    # #  #   # #     #       #         #   # #   # #   # ##  #
  #   ##### ####  #  ## ####    #         #   # #   # # # # # # #
  #   #   # #  #  #   # #       #         #   # #   # # # # #  ##
  #   #   # #   #  #### #####   #         ####   ###   # #  #   #
```

## How it works

Two pieces, one repository:

- **`target/app.py`** — a deliberately vulnerable web application. Pure Python
  standard library, no dependencies. It has SQL injection, command injection,
  path traversal, IDOR, reflected XSS and an uncapped memory endpoint, and it
  happily serves its own `.env`.
- **`hackwatch`** — the client. POSIX `sh` + `curl`. It runs on the watch, on a
  laptop, anywhere. Every response from the lab carries an `X-HackWatch-Lab`
  header; the client refuses to run any attack command unless it sees that
  header, so it can only ever hit the lab.

## Requirements

- The lab: `python3` (3.8+). Nothing else.
- The client: `sh`, `curl`. Optional, for the wrist: Wear Term's `wt-vibrate`,
  `wt-notify`, `wt-tts`.

## Quickstart

**1. Start the lab** on a machine on the same Wi-Fi as the watch:

```sh
git clone https://github.com/0xberkay/hackwatch.git
cd hackwatch
python3 target/app.py            # listens on 0.0.0.0:8000
```

On the watch, reach it at the machine's LAN address, e.g. `http://192.168.1.20:8000`.

If the watch times out but can ping the machine, a firewall is in the way. On a
machine running `ufw`:

```sh
sudo ufw allow 8000/tcp
```

**2. Install the client** (on the watch, inside Wear Term, or on your laptop):

```sh
./install.sh                     # -> ~/.local/bin/hackwatch
# or just run it in place: ./hackwatch ...
```

**3. Point it at the lab and go:**

```sh
hack                           # finds the lab, runs everything, drops the site
```

`hack` scans the LAN for the lab the first time and remembers it, so the next
run starts instantly. Step by step, if you prefer:

```sh
hackwatch target http://192.168.1.20:8000
hackwatch recon                  # fingerprint + exposed files
hackwatch sqli                   # ' OR 1=1--  -> ACCESS GRANTED
hackwatch loot                   # dump the users table
hackwatch nuke --yes             # wipe the DB and kill the server
```

Or skip the steps: `hack` runs the full chain with no stops and drops the
site. Typing a URL on a watch is miserable, which is why `target` remembers
it.

## Commands

| Command | What it does |
| --- | --- |
| `hackwatch target <url>` | remember the lab URL |
| `hackwatch status` | is the lab up? |
| `hackwatch recon` | server/title fingerprint and well-known path probe |
| `hackwatch sqli` | login bypass via SQL injection |
| `hackwatch loot` | dump the `users` table through a UNION injection |
| `hackwatch cmdi <cmd>` | run a shell command on the target (command injection) |
| `hackwatch lfi <path>` | read a file off the target (path traversal) |
| `hackwatch shell` | interactive shell over the command injection |
| `hackwatch nuke --yes` | wipe the database and kill the server |
| `hackwatch auto --yes` | full chain with no stops: recon, sqli, loot, nuke |
| `hack` | same as `auto --yes`: one word, total compromise |
| `hackwatch banner` | print the banner |

Environment: `HACKWATCH_PLAIN=1` disables colour, `HACKWATCH_COLOR=1` forces it
when the output is piped.

## What `nuke` actually does

1. Verifies the target is the lab (`X-HackWatch-Lab` header).
2. Reads `/.env` to learn the absolute path of the SQLite database.
3. Sends `rm -f <db>; kill -9 $PPID` through the command-injection endpoint at
   `/ping?host=`. The `$PPID` of the injected shell is the lab server, so the
   database is deleted and the process is killed.
4. Polls the target until it stops answering and prints **TARGET DOWN**.
5. If the RCE failed, falls back to the uncapped allocation at `/boom`.

The result: the accounts are gone, the process is gone, the site is gone.

## Wrist integration

When Wear Term's device commands are on `PATH`, `hackwatch` uses them without
being asked: a short buzz per path found by `recon`, a long one on
`ACCESS GRANTED`, a notification and a spoken "target down" when `nuke`
finishes. On any other machine those calls silently do nothing.

## Layout

```
hackwatch/
├── hackwatch        # the client (POSIX sh + curl)
├── target/
│   ├── app.py       # the vulnerable lab app (stdlib only)
│   └── files/       # files the app serves
├── install.sh
├── docs/lab.md      # every vulnerability, its exploit and its fix
└── LICENSE
```

## Ethics

This is a teaching tool. The vulnerable app exists so that breaking into
something can be *demonstrated* safely.

- Run the lab on a network you control and take it down only when you mean to.
- `hackwatch` refuses to attack anything that does not identify itself as the
  lab. Do not remove that check to use it elsewhere.
- Attacking a system you do not own is a crime in most countries. Do not be
  that person.

## License

MIT. See [LICENSE](LICENSE).
