#!/usr/bin/env python3
"""thread: long-lived units of work for a coding agent, after GrepMem (arXiv 2611.25123).

A thread is an append-only plain-text log, a current summary and a little metadata,
all under ~/.threads/<id>/. Standard library only, no network. See README.md.
"""
import argparse
import glob
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

CAP = 6000  # max characters printed back to the agent per page (the paper's figure)
HDR = re.compile(r"^=== (\S+) (\S+) (\S+)(?: (.*))? ===$")  # time, session, entry type, tool name


def home():
    return Path(os.environ.get("THREADS_HOME") or Path.home() / ".threads")


def die(msg):
    print(f"thread: {msg}", file=sys.stderr)
    sys.exit(1)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write(path, text):
    home().mkdir(parents=True, exist_ok=True, mode=0o700)  # mkdir's mode covers only the leaf
    os.chmod(home(), 0o700)  # also when the directory was there already
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")  # unique, so parallel writers cannot collide
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def entry(ts, sid, kind, body, extra=""):
    head = f"=== {ts} {(sid or '-')[:8]} {kind}{' ' + extra if extra else ''} ==="
    # a body line that looks like a header is indented so the log stays parseable
    lines = [" " + l if l.startswith("=== ") else l for l in str(body).splitlines()]
    return head + "\n" + "\n".join(lines) + "\n"


def append(tid, text):
    # one O_APPEND write per call, so entries from concurrent sessions do not interleave mid-entry
    fd = os.open(home() / tid / "log.txt", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, text.encode("utf-8", "replace"))  # a lone surrogate must not stop capture
    finally:
        os.close(fd)


# ---- threads ----

def meta(tid):
    return json.loads((home() / tid / "meta.json").read_text(encoding="utf-8"))


def save_meta(m):
    write(home() / m["id"] / "meta.json", json.dumps(m, indent=1))


def all_ids():
    return sorted(p.parent.name for p in home().glob("*/meta.json"))


def resolve(ref):
    ids = all_ids()
    if ref in ids:
        return ref
    hits = [i for i in ids if i.startswith(ref)]
    if len(hits) != 1:
        die(f"no thread '{ref}'" if not hits else f"'{ref}' is ambiguous: {', '.join(hits)}")
    return hits[0]


def is_open(tid):
    try:
        return meta(tid)["status"] == "open"
    except (OSError, ValueError, KeyError):
        return False  # removed or unreadable


def summary(tid):
    p = home() / tid / "summary.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def entries(tid):
    """Yield (lineno, ts, session, kind, extra, body) for each entry in the log."""
    p = home() / tid / "log.txt"
    if not p.exists():
        return
    cur = None
    with open(p, encoding="utf-8", errors="replace") as f:
        for n, line in enumerate(f, 1):
            m = HDR.match(line.rstrip("\n"))
            if m:
                if cur:
                    yield (*cur[:5], "".join(cur[5]).rstrip("\n"))
                cur = [n, m[1], m[2], m[3], m[4] or "", []]
            elif cur:
                cur[5].append(line)
    if cur:
        yield (*cur[:5], "".join(cur[5]).rstrip("\n"))


# ---- sessions and capture ----

def session_id():
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or ""


def state_path(sid):
    if not re.fullmatch(r"[\w-]+", sid or ""):  # sid becomes a file name
        return None
    return home() / ".sessions" / f"{sid}.json"


def state(sid):
    p = state_path(sid)
    try:
        return json.loads(p.read_text()) if p and p.exists() else None
    except ValueError:
        return None  # corrupt state file: start over rather than crash every command


def active(sid):
    tid = (state(sid) or {}).get("thread")
    return tid if tid and is_open(tid) else None  # a thread closed or removed elsewhere is not active


def find_transcript(sid):
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    hits = glob.glob(os.path.join(glob.escape(base), "projects", "*", f"{sid}.jsonl"))
    return hits[0] if hits else None


def flat(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict):
            out.append(b.get("text", "") if b.get("type") == "text" else f"[{b.get('type')}]")
    return "\n".join(out)


GREP_CALL = re.compile(r"\bthread(\.py)?[\"']?\s+grep\b")
GREP_MARK = "[output of `thread grep` not stored: it only repeats this log]"


def render(line, own=None, greps=None):
    """One transcript JSONL line -> log entries. Raises on a line it cannot read.

    `own` is the session being captured: a forked or resumed session's file also holds its
    parent's lines, which the parent already captured. `greps` collects the ids of
    `thread grep` calls, whose results are replaced by GREP_MARK.

    shortcut: reads Claude Code's transcript JSONL, which is not a documented format;
    revisit when a Claude Code release changes it (tests/test_thread.py pins the shape).
    """
    if not line.strip():
        return ""
    d = json.loads(line)
    if not isinstance(d, dict) or d.get("type") not in ("user", "assistant") or d.get("isSidechain"):
        return ""
    if own and d.get("sessionId") and d["sessionId"] != own:
        return ""
    greps = [] if greps is None else greps
    ts, sid, role = d.get("timestamp") or now(), d.get("sessionId"), d["type"]
    content = (d.get("message") or {}).get("content")
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    out = []
    for b in content or []:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text":
            out.append(entry(ts, sid, role, b.get("text", "")))
        elif t == "thinking":
            if b.get("thinking"):
                out.append(entry(ts, sid, "thinking", b["thinking"]))
        elif t == "tool_use":
            inp = b.get("input")
            if isinstance(inp, dict) and GREP_CALL.search(str(inp.get("command", ""))):
                greps.append(b.get("id"))
            out.append(entry(ts, sid, "tool_use", json.dumps(inp, ensure_ascii=False),
                             str(b.get("name", "")).replace("\n", " ")))
        elif t == "tool_result":
            if b.get("tool_use_id") in greps:
                greps.remove(b["tool_use_id"])
                out.append(entry(ts, sid, "tool_result", GREP_MARK))
            else:
                out.append(entry(ts, sid, "tool_result", flat(b.get("content"))))
        else:
            out.append(entry(ts, sid, role, f"[{t}]"))  # images and other binary blocks
    return "".join(out)


def capture(sid, tpath=None):
    """Append the uncaptured part of the session transcript to the session's active thread."""
    st = state(sid)
    if not st:
        return
    tid = st.get("thread")
    if tid and not is_open(tid):
        tid = st["thread"] = None  # closed by another session, or removed: stop capturing into it
    tpath = tpath or find_transcript(sid)
    if tpath and os.path.exists(tpath):
        with open(tpath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if lines and not lines[-1].endswith("\n"):
            lines.pop()  # half-written line; take it next time
        first = st.get("offset", 0)
        if first > len(lines):
            first = 0  # the transcript was replaced by a shorter one
        parts, greps = [], st.setdefault("greps", [])
        for n, line in enumerate(lines[first:] if tid else [], first + 1):
            try:
                parts.append(render(line, sid, greps))
            except Exception as e:  # an unknown line shape must not block the lines after it
                parts.append(entry(now(), sid, "event",
                                   f"capture skipped transcript line {n}: {type(e).__name__}"))
        if "".join(parts):
            append(tid, "".join(parts))
        # shortcut: no lock, two captures of one session at the same instant can duplicate
        # entries; add a lock file if that ever shows up in a log.
        st["offset"] = len(lines)  # with no thread (detached) the lines are skipped for good
    write(state_path(sid), json.dumps(st))


def detach(sid):
    st = state(sid)
    if st:
        st["thread"] = None
        write(state_path(sid), json.dumps(st))


def bind(sid, tid):
    """Point the session at a thread. The transcript so far goes to the previous thread;
    a session that never had a thread is captured from its start (backfill)."""
    if not state_path(sid):
        print("(no Claude Code session id: nothing bound, nothing will be captured)")
        return
    capture(sid)
    st = state(sid) or {"offset": 0}
    st["thread"] = tid
    write(state_path(sid), json.dumps(st))
    capture(sid)


def try_capture(sid):
    """Capture ahead of a deliberate entry; a failure must not cost the entry itself."""
    try:
        capture(sid)
    except Exception as e:
        print(f"thread: capture failed ({type(e).__name__}: {e}); continuing", file=sys.stderr)


def target(args):
    if getattr(args, "thread", None):
        return resolve(args.thread)
    tid = active(session_id())
    if not tid:
        die("no active thread: run `thread open <id>` or pass -t <id>")
    return tid


def read_text(parts):
    parts = parts[1:] if parts[:1] == ["--"] else parts
    if not parts and sys.stdin.isatty():
        die("no text: pass it as arguments or on stdin")
    text = " ".join(parts) if parts else sys.stdin.read()
    if not text.strip():
        die("empty text")
    return text.strip()


# ---- commands ----

def show(tid):
    m = meta(tid)
    print(f"# {m['title']}  [{tid}]  kind={m['kind'] or '-'}  status={m['status']}\n")
    print(summary(tid).strip() or "(no checkpoint yet)")
    since = []
    for e in entries(tid):
        if e[3] == "checkpoint":
            since = []
        elif e[3] != "event":
            since.append(e)
    if not since:
        return
    notes = [e for e in since if e[3] == "note"]
    msgs = [e for e in since if e[3] in ("user", "assistant")][-6:]
    text = "\n".join(f"[{e[1]} {e[3]}] {e[5][:600]}" for e in sorted(notes + msgs))
    if len(text) > CAP:
        text = "…" + text[-CAP:]
    print(f"\n-- {len(since)} entries since the last checkpoint; notes and latest messages: --")
    print(text)
    print("-- `thread grep <regex>` for more; `thread checkpoint` once caught up --")


def cmd_new(a):
    title = " ".join(" ".join(a.title).split())  # one line, single spaces
    if not title:
        die("empty title")
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50] or "thread"
    tid, n = base, 1
    while (home() / tid).exists():
        n += 1
        tid = f"{base}-{n}"
    save_meta({"id": tid, "title": title, "kind": a.kind or "", "status": "open",
               "created": now(), "cwd": os.getcwd()})
    sid = session_id()
    bind(sid, tid)
    append(tid, entry(now(), sid, "event", f"created: {title}"))
    print(f"created thread {tid}")


def cmd_open(a):
    tid = resolve(a.id)
    show(tid)  # before binding, so the backfill of this session is not echoed back
    if meta(tid)["status"] == "closed":
        print(f"\n(closed: shown read-only, not bound; `thread reopen {tid}` to resume it)")
    else:
        bind(session_id(), tid)


def cmd_reopen(a):
    tid = resolve(a.id)
    sid = session_id()
    capture(sid)  # while it is still closed, so what a bound session did meanwhile stays out
    m = meta(tid)
    m["status"] = "open"
    save_meta(m)
    bind(sid, tid)
    append(tid, entry(now(), sid, "event", "reopened"))
    print(f"reopened thread {tid}")


def cmd_note(a):
    tid, text, sid = target(a), read_text(a.text), session_id()
    try_capture(sid)  # keep the log chronological
    append(tid, entry(now(), sid, "note", text))


def cmd_checkpoint(a, close=False):
    tid, text, sid = target(a), read_text(a.text), session_id()
    if not is_open(tid):
        die(f"thread {tid} is closed; only notes can be added. `thread reopen {tid}` first")
    try_capture(sid)
    write(home() / tid / "summary.md", text + "\n")
    append(tid, entry(now(), sid, "checkpoint", text))
    if close:
        mine = active(sid) == tid
        m = meta(tid)
        m["status"] = "closed"
        save_meta(m)
        append(tid, entry(now(), sid, "event", "closed"))
        if mine:
            detach(sid)  # other sessions bound to it are detached at their next capture
    print(f"{'closed' if close else 'checkpointed'} thread {tid}")


def cmd_close(a):
    cmd_checkpoint(a, close=True)


def cmd_detach(a):
    sid = session_id()
    if not (state(sid) or {}).get("thread"):  # also clears a binding to a thread closed elsewhere
        die("no active thread")
    capture(sid)
    detach(sid)
    print("detached: this session is no longer captured")


def clip(line, start=0):
    if len(line) <= 400:
        return line
    s = max(0, start - 150)
    return ("…" if s else "") + line[s:s + 400] + "…"


def cmd_grep(a):
    try:
        rx = re.compile(a.pattern, re.I)
    except re.error as e:
        die(f"bad regex: {e}")
    cur = active(session_id())
    if a.offset <= 0:
        capture(session_id())  # page 1 sees the turn in progress; later pages need a stable log
    hits = []  # (tid, lineno, header, [context lines])
    ctx = min(max(a.context, 0), 3)
    # the active thread goes last: it is the only one that grows between pages
    for tid in (sorted(all_ids(), key=lambda t: t == cur) if a.all else [target(a)]):
        p = home() / tid / "log.txt"
        if not p.exists():
            continue
        # shortcut: reads the whole log into memory; stream it if logs reach hundreds of MB
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        head = ""
        for i, line in enumerate(lines):
            if HDR.match(line):
                head = line
            m = rx.search(line)
            if m:
                block = [("> " if j == i else "  ") + clip(lines[j], m.start() if j == i else 0)
                         for j in range(max(0, i - ctx), min(len(lines), i + ctx + 1))]
                hits.append((tid, i + 1, head, block))
    if a.count:
        print(len(hits))
        return
    start, size = max(a.offset, 0), min(max(a.max, 1), 30)
    out, used = [], 0
    for tid, n, head, block in hits[start:start + size]:
        piece = f"{tid}:{n}  {head}\n" + "\n".join(block)
        if out and used + len(piece) > CAP:
            break  # the page ends early; the footer points at the first match not shown
        out.append(piece)
        used += len(piece) + 4
    if out:
        print("\n--\n".join(out))
    end = start + len(out)
    more = f"; next page: --offset {end}" if end < len(hits) else ""
    print(f"[matches {start + 1 if out else 0}-{end if out else 0} of {len(hits)}{more}]")


def cmd_list(a):
    cur = active(session_id())
    rows = []
    for tid in all_ids():
        try:
            m = meta(tid)
        except (OSError, ValueError):
            continue  # unreadable meta.json: leave it out rather than fail the listing
        if (m["status"] == "open" or a.all) and (not a.kind or m["kind"] == a.kind):
            log = home() / tid / "log.txt"
            t = log.stat().st_mtime if log.exists() else 0
            rows.append((t, f"{'*' if tid == cur else ' '} {tid}  {m['kind'] or '-'}  {m['status']}  "
                            f"{time.strftime('%Y-%m-%d', time.localtime(t))}  {m['title']}"))
    print("\n".join(r for _, r in sorted(rows, reverse=True)) or "(no threads)")


def cmd_export(a):
    tid = resolve(a.id)
    m = meta(tid)
    print(f"# {m['title']}\n\n`{tid}` · kind: {m['kind'] or '-'} · status: {m['status']} · "
          f"created: {m['created']}\n\n## Summary\n\n{summary(tid).strip() or '(none)'}\n\n## Notes\n")
    for e in entries(tid):
        if e[3] == "note":
            print(f"- {e[1]}: {e[5]}")


def cmd_hook(a):
    """Claude Code hook entry point. Never fails the session: errors go to errors.log."""
    try:
        d = json.load(sys.stdin)
        sid = d.get("session_id") or ""
        if not state_path(sid):
            return
        capture(sid, d.get("transcript_path"))
        tid = active(sid)
        if d.get("hook_event_name") == "SessionStart" and tid:
            print(f"Active thread: {tid} ({meta(tid)['title']}). Details lost to compaction are in "
                  f"its log: run `thread grep <regex>` before re-deriving anything.\n\n"
                  # Claude Code keeps only a preview of hook output above 10,000 characters
                  f"Thread summary:\n{summary(tid).strip()[:CAP] or '(no checkpoint yet)'}")
    except Exception:
        try:
            home().mkdir(parents=True, exist_ok=True, mode=0o700)
            log = home() / "errors.log"
            big = log.exists() and log.stat().st_size > 1_000_000  # start over, do not grow forever
            fd = os.open(log, os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if big else os.O_APPEND), 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"{now()}\n{traceback.format_exc()}\n")
        except OSError:
            pass


def main(argv=None):
    p = argparse.ArgumentParser(prog="thread", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, help, thread=False):
        s = sub.add_parser(name, help=help)
        s.set_defaults(fn=fn)
        if thread:
            s.add_argument("-t", "--thread", help="thread id (default: the session's active thread)")
        return s

    s = cmd("new", cmd_new, "create a thread and make it this session's active thread")
    s.add_argument("title", nargs="+")
    s.add_argument("--kind", help="free-text label: project, feature, idea, bug, ...")
    cmd("open", cmd_open, "show a thread and make it active").add_argument("id")
    cmd("reopen", cmd_reopen, "reopen a closed thread and make it active").add_argument("id")
    # REMAINDER: words after the first are text even when they look like flags; -t goes before the text
    s = cmd("note", cmd_note, "append a note to the log (text, or stdin)", thread=True)
    s.add_argument("text", nargs=argparse.REMAINDER)
    s = cmd("checkpoint", cmd_checkpoint, "replace the summary (text, or stdin)", thread=True)
    s.add_argument("text", nargs=argparse.REMAINDER)
    s = cmd("close", cmd_close, "close a thread with a final summary (text, or stdin)", thread=True)
    s.add_argument("text", nargs=argparse.REMAINDER)
    cmd("detach", cmd_detach, "stop capturing this session")
    s = cmd("grep", cmd_grep, "regex search of the log (case-insensitive)", thread=True)
    s.add_argument("pattern")
    s.add_argument("--all", action="store_true", help="search every thread, open and closed")
    s.add_argument("--count", action="store_true", help="print only the number of matches")
    s.add_argument("--max", type=int, default=10, help="matches per page (default 10, max 30)")
    s.add_argument("--offset", type=int, default=0, help="skip this many matches")
    s.add_argument("--context", type=int, default=1, help="context lines (default 1, max 3)")
    s = cmd("list", cmd_list, "list open threads")
    s.add_argument("--all", action="store_true", help="include closed threads")
    s.add_argument("--kind")
    cmd("export", cmd_export, "print the summary and all notes as markdown").add_argument("id")
    cmd("hook", cmd_hook, "Claude Code hook entry point (reads the hook JSON on stdin)")

    for s in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):  # Windows pipes default to the locale code page
            s.reconfigure(encoding="utf-8", errors="replace")
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
