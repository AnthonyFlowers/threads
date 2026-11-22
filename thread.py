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
    with os.fdopen(fd, "w", encoding="utf-8", errors="replace", newline="\n") as f:
        f.write(text)
    for attempt in range(40):
        try:
            return os.replace(tmp, path)
        except PermissionError:  # Windows: another process (a hook, antivirus) has the target open
            if attempt == 39:
                os.unlink(tmp)
                raise
            time.sleep(0.025)


def read(path):
    for attempt in range(40):
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:  # Windows: the file is being replaced at this moment
            if attempt == 39:
                raise
            time.sleep(0.025)


def printable(s):
    """Log text goes back to a terminal and into the agent's context: drop control characters."""
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", s)


def entry(ts, sid, kind, body, extra=""):
    head = f"=== {ts} {(sid or '-')[:8]} {kind}{' ' + extra if extra else ''} ==="
    # a body line that looks like a header is indented so the log stays parseable
    lines = [" " + l if l.startswith("=== ") else l for l in str(body).splitlines()]
    return head + "\n" + "\n".join(lines) + "\n"


def append(tid, text):
    # one append-mode write per call, so entries from concurrent sessions do not interleave mid-entry
    path = str(home() / tid / "log.txt")
    if os.name == "nt":
        # the C runtime's O_APPEND seeks and then writes, and text mode splits the write at each
        # newline: parallel writers lose data. FILE_APPEND_DATA appends atomically in the kernel.
        import ctypes
        import msvcrt
        create = ctypes.windll.kernel32.CreateFileW
        create.restype = ctypes.c_void_p
        create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                           ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        handle = create(path, 0x4, 0x7, None, 4, 0x80, None)  # append, share all, OPEN_ALWAYS
        if handle in (None, ctypes.c_void_p(-1).value):
            raise ctypes.WinError()
        fd = msvcrt.open_osfhandle(handle, os.O_BINARY)
    else:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, text.encode("utf-8", "replace"))  # a lone surrogate must not stop capture
    finally:
        os.close(fd)


# ---- threads ----

def meta(tid):
    return json.loads(read(home() / tid / "meta.json"))


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
    except (OSError, ValueError, KeyError, TypeError):
        return False  # removed or unreadable


def generation(tid):
    """Changes when a thread is closed or replaced by a new one of the same id, so a session
    bound before that is not captured into what came after."""
    m = meta(tid)
    return f"{m.get('uid')}/{m.get('closes', 0)}"


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
        st = json.loads(read(p)) if p and p.exists() else None
    except ValueError:
        st = None
    return st if isinstance(st, dict) else None  # corrupt state file: start over, do not crash


def bound(st):
    """The thread a session state is validly bound to, or None."""
    tid = (st or {}).get("thread")
    if isinstance(tid, str) and is_open(tid) and st.get("gen") == generation(tid):
        return tid
    return None  # detached, or the thread was closed or removed since this session bound to it


def active(sid):
    return bound(state(sid))


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


# `thread grep` in command position: at the start of a line or after ; & | ( and, optionally,
# VAR=value assignments, a python launcher and a path. A mere mention in an argument does not count.
GREP_CALL = re.compile(r"""(?m)(?:^|[;&|(])\s*(?:\w+=\S*\s+)*(?:\S*py\S*\s+)?["']?(?:\S*[/\\])?"""
                       r"""thread(?:\.py|\.cmd)?["']?\s+grep\b""")
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
    if d.get("isMeta") or d.get("isCompactSummary"):
        return ""  # injected by Claude Code (skill bodies, reminders, its compaction summary)
    if own and d.get("sessionId") and d["sessionId"] != own:
        return ""
    greps = [] if greps is None else greps
    ts, sid, role = "".join(str(d.get("timestamp") or now()).split()), d.get("sessionId"), d["type"]
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
            if isinstance(inp, dict) and b.get("id") and GREP_CALL.search(str(inp.get("command", ""))):
                greps.append(b["id"])
                del greps[:-50]  # calls that never got a result must not pile up
            out.append(entry(ts, sid, "tool_use", json.dumps(inp, ensure_ascii=False),
                             " ".join(str(b.get("name", "")).split())))
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
    tid = st["thread"] = bound(st)  # None also when it was closed or removed by another session
    tpath = tpath or find_transcript(sid)
    if tpath and os.path.exists(tpath):
        with open(tpath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if lines and not lines[-1].endswith("\n"):
            lines.pop()  # half-written line; take it next time
        first = st.get("offset", 0)
        if not isinstance(first, int) or not 0 <= first <= len(lines):
            first = 0  # the transcript was replaced by a shorter one, or the state is damaged
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
    st["thread"], st["gen"] = tid, generation(tid)
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


def stdin_ready(seconds=5):
    """False when stdin is an open pipe that sends nothing: an agent's shell can hand over one
    that never ends, and reading it would wait forever."""
    try:
        if os.name == "nt":
            import ctypes
            import msvcrt
            handle = ctypes.c_void_p(msvcrt.get_osfhandle(sys.stdin.fileno()))
            waiting, end = ctypes.c_ulong(), time.time() + seconds
            while time.time() < end:
                peek = ctypes.windll.kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(waiting), None)
                if not peek or waiting.value:
                    return True  # not a pipe, a closed pipe, or data is waiting
                time.sleep(0.05)
            return False
        import select
        return bool(select.select([sys.stdin], [], [], seconds)[0])
    except (ValueError, OSError, TypeError, AttributeError):
        return True  # not a real file (tests), or it cannot be watched


def read_text(parts):
    parts = parts[1:] if parts[:1] == ["--"] else parts
    if not parts:
        if sys.stdin is None or sys.stdin.isatty():
            die("no text: pass it as arguments or on stdin")
        if not stdin_ready():
            die("no text arrived on stdin within 5 s: pass it as arguments or a heredoc")
    text = (" ".join(parts) if parts else sys.stdin.read()).lstrip("\ufeff")  # PowerShell may add a BOM
    if not text.strip():
        die("empty text")
    return text.strip()


# ---- commands ----

def since_checkpoint(tid):
    since = []
    for e in entries(tid):
        if e[3] == "checkpoint":
            since = []
        elif e[3] != "event":
            since.append(e)
    return since


def show(tid):
    m = meta(tid)
    print(f"# {m['title']}  [{tid}]  kind={m['kind'] or '-'}  status={m['status']}\n")
    print(printable(summary(tid).strip()) or "(no checkpoint yet)")
    since = since_checkpoint(tid)
    if not since:
        return
    notes = [e for e in since if e[3] == "note"]
    msgs = [e for e in since if e[3] in ("user", "assistant")][-6:]
    text = printable("\n".join(f"[{e[1]} {e[3]}] {e[5][:600]}" for e in sorted(notes + msgs)))
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
               "created": now(), "cwd": os.getcwd(), "uid": os.urandom(4).hex()})
    sid = session_id()
    was = active(sid)
    bind(sid, tid)
    append(tid, entry(now(), sid, "event", f"created: {title}"))
    print(f"created thread {tid}" + (f"; this session is now captured into it, no longer into {was}"
                                     if was else ""))


def cmd_open(a):
    tid = resolve(a.id)
    show(tid)  # before binding, so the backfill of this session is not echoed back
    if meta(tid)["status"] == "closed":
        print(f"\n(closed: shown read-only, not bound; `thread reopen {tid}` to work on it again)")
    else:
        bind(session_id(), tid)


def cmd_reopen(a):
    tid = resolve(a.id)
    if is_open(tid):
        die(f"thread {tid} is already open; use `thread open {tid}`")
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
    print(f"noted in {tid} ({len(since_checkpoint(tid))} entries since the last checkpoint)")


def cmd_checkpoint(a, close=False):
    tid, text, sid = target(a), read_text(a.text), session_id()
    if not is_open(tid):
        die(f"thread {tid} is closed; only notes can be added. `thread reopen {tid}` first")
    try_capture(sid)
    if len(text) > CAP:
        print(f"thread: summary is {len(text)} characters; only the first {CAP} are re-injected "
              f"after a compaction", file=sys.stderr)
    append(tid, entry(now(), sid, "checkpoint", text))  # the log first: it is the record
    write(home() / tid / "summary.md", text + "\n")
    if close:
        mine = active(sid) == tid
        m = meta(tid)
        m["status"], m["closes"] = "closed", m.get("closes", 0) + 1
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
    line = printable(line)
    if len(line) <= 400:
        return line
    s = max(0, start - 150)
    return ("…" if s else "") + line[s:s + 400] + "…"


def cmd_grep(a):
    try:
        rx = re.compile(a.pattern, re.I)
    except re.error as e:
        die(f"bad regex: {e}")
    if a.all and a.thread:
        die("use --all or -t, not both")
    if a.offset <= 0:
        try_capture(session_id())  # page 1 sees the turn in progress; later pages need a stable log
    hits, total = [], 0  # hits: (tid, lineno, header, [context lines])
    ctx = min(max(a.context, 0), 3)
    for tid in (all_ids() if a.all else [target(a)]):
        p = home() / tid / "log.txt"
        if not p.exists():
            continue
        # shortcut: reads the whole log into memory; stream it if logs reach hundreds of MB
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        heads = [bool(HDR.match(l)) for l in lines]
        head, own_call = "", False
        for i, line in enumerate(lines):
            if heads[i]:
                head, own_call = line, False
            elif head.split()[3:4] == ["tool_use"] and i and lines[i - 1] is head:
                # an earlier `thread grep` call holds its own pattern: leaving it out keeps
                # the match count from growing with every page
                try:
                    own_call = bool(GREP_CALL.search(str(json.loads(line).get("command", ""))))
                except (ValueError, AttributeError):
                    own_call = False
            m = None if own_call else rx.search(line)
            if m and a.count:
                total += 1
            elif m:
                lo = hi = i  # context stays inside the entry: a neighbour's text is not this match's
                while i - lo < ctx and lo > 0 and not heads[lo] and not heads[lo - 1]:
                    lo -= 1
                while hi - i < ctx and hi + 1 < len(lines) and not heads[hi + 1]:
                    hi += 1
                block = [("> " if j == i else "  ") + clip(lines[j], m.start() if j == i else 0)
                         for j in range(lo, hi + 1)]
                hits.append((tid, i + 1, head, block))
    if a.count:
        print(total)
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
            if (m["status"] == "open" or a.all) and (not a.kind or m["kind"] == a.kind):
                log = home() / tid / "log.txt"
                t = log.stat().st_mtime if log.exists() else 0
                rows.append((t, f"{'*' if tid == cur else ' '} {tid}  {m['kind'] or '-'}  {m['status']}"
                                f"  {time.strftime('%Y-%m-%d', time.localtime(t))}  {m['title']}"))
        except (OSError, ValueError, KeyError, TypeError):
            continue  # unreadable meta.json: leave it out rather than fail the listing
    print("\n".join(r for _, r in sorted(rows, reverse=True)) or "(no threads)")
    if (home() / "errors.log").exists():
        print(f"(hook errors are recorded in {home() / 'errors.log'})")


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
            text, stale = printable(summary(tid).strip()), len(since_checkpoint(tid))
            print(f"Active thread: {tid} ({meta(tid)['title']}). Details lost to compaction are in "
                  f"its log: run `thread grep <regex>` before re-deriving anything.\n\n"
                  # Claude Code keeps only a preview of hook output above 10,000 characters
                  f"Thread summary:\n{text[:CAP] or '(no checkpoint yet)'}"
                  + (f"\n…[cut at {CAP} characters; `thread open {tid}` prints all of it]"
                     if len(text) > CAP else "")
                  + (f"\n\n{stale} entries were logged after this summary, so it may be out of date: "
                     f"write a fresh `thread checkpoint` now." if stale or not text else ""))
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
