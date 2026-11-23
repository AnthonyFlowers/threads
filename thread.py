#!/usr/bin/env python3
"""thread: long-lived units of work for a coding agent, after GrepMem (arXiv 2611.25123).

A thread is an append-only plain-text log, a current summary and a little metadata,
all under ~/.threads/<id>/. Standard library only, no network. See README.md.
"""
import argparse
import contextlib
import glob
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

CAP = 6000  # max characters printed back to the agent per page (the paper's figure)
TYPES = ("user", "assistant", "thinking", "tool_use", "tool_result", "subagent", "notification",
         "compaction", "note", "checkpoint", "event")
HDR = re.compile(r"^=== (\S+) (\S+) (\S+)(?: (.*))? ===$")  # time, session, entry type, tool name


def home():
    return Path(os.environ.get("THREADS_HOME") or Path.home() / ".threads")


def die(msg):
    print(f"thread: {msg}", file=sys.stderr)
    sys.exit(1)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write(path, text):
    made = not home().exists()
    home().mkdir(parents=True, exist_ok=True, mode=0o700)  # mkdir's mode covers only the leaf
    if made or not os.environ.get("THREADS_HOME"):
        os.chmod(home(), 0o700)  # ~/.threads is always private; a THREADS_HOME that was there keeps its mode
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
    return re.sub("[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]", "", s)  # C0, C1, bidi overrides


def entry(ts, sid, kind, body, extra=""):
    sid = "".join(str(sid or "-").split())[:8] or "-"
    head = f"=== {ts} {sid} {kind}{' ' + extra if extra else ''} ==="
    # a body line that looks like a header, also once it is printed, is indented: the log stays
    # parseable and a captured line cannot pass for an entry header
    lines = [" " + l if printable(l).startswith("=== ") else l for l in str(body).splitlines()]
    return head + "\n" + "\n".join(lines) + "\n"


def append(tid, text):
    # one append-mode write per call, so entries from concurrent sessions do not interleave mid-entry
    path = str(home() / tid / "log.txt")
    if os.name == "nt":
        # the C runtime's O_APPEND seeks and then writes, and text mode splits the write at each
        # newline: parallel writers lose data. FILE_APPEND_DATA appends atomically in the kernel.
        import ctypes
        import msvcrt
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create = k32.CreateFileW
        create.restype = ctypes.c_void_p
        create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                           ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        handle = create(path, 0x4, 0x7, None, 4, 0x80, None)  # append, share all, OPEN_ALWAYS
        if handle in (None, ctypes.c_void_p(-1).value):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_BINARY)
        except OSError:
            k32.CloseHandle(ctypes.c_void_p(handle))
            raise
    else:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        data = text.encode("utf-8", "replace")  # a lone surrogate must not stop capture
        while data:  # normally one write; a short write (full disk) must not cut an entry silently
            data = data[os.write(fd, data):]
    finally:
        os.close(fd)


# ---- threads ----

def meta(tid):
    m = json.loads(read(home() / tid / "meta.json"))  # invalid JSON or encoding is a ValueError too
    if not isinstance(m, dict) or any(k not in m for k in ("id", "title", "kind", "status")):
        raise ValueError(f"the meta.json of thread {tid} is damaged")
    return m


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
    except (OSError, ValueError):
        return False  # removed or unreadable


def generation(tid):
    """Changes when a thread is closed or replaced by a new one of the same id, so a session
    bound before that is not captured into what came after."""
    m = meta(tid)
    return f"{m.get('uid')}/{m.get('closes', 0)}"


def summary(tid):
    p = home() / tid / "summary.md"
    return read(p) if p.exists() else ""


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
    except (ValueError, FileNotFoundError):
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
GREP_CALL = re.compile(
    r"""(?m)(?:^|[;&|({!`])\s*"""                                               # command position
    r"""(?:(?:rtk|time|command|exec|xargs|sudo|do|then|else|timeout\s+\S+)\s+"""
    r"""|(?:\S*/)?env\s+(?:-u\s+\S+\s+|-\S+\s+)*)*"""
    r"""(?:\w+=\S*\s+)*"""                                                      # VAR=value
    r"""(?:(?:\S*python[\d.]*(?:\.exe)?|py(?:\.exe)?)\s+(?:-\S+\s+)*|uv\s+run\s+)?"""  # launcher
    r"""["']?(?:\S*[/\\])?thread(?:\.py|\.cmd)?["']?\s+grep(?=\s|$)""")
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b", re.S)
QUOTED = re.compile(r"""'[^']*'|"(?:[^"\\]|\\.)*\"""")


def runs_grep(command):
    """True when a shell command runs `thread grep`. Text that only mentions it (a heredoc body,
    a quoted commit message) does not count."""
    command = HEREDOC.sub("", command)
    command = QUOTED.sub(lambda m: "''" if "grep" in m[0] else m[0], command)
    return bool(GREP_CALL.search(command))


def tool_input(inp):
    """A tool call as `key: value` lines, strings raw: commands and paths are searchable as typed."""
    if not isinstance(inp, dict):
        return json.dumps(inp, ensure_ascii=False)
    return "\n".join(f"{k}: {v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)}"
                     for k, v in inp.items())


REPORT = ("Another Claude session sent a message", "<agent-message", "<cross-session-message")


def render(line, own=None, since=None, seen=None):
    """One transcript JSONL line -> log entries. Raises on a line it cannot read.

    `own` is the session being captured; lines that carry another session's id belong to that
    session's own transcript. `since` is the moment a forked session began: its file starts with
    a copy of the parent's lines (under the fork's id, with their old timestamps).

    shortcut: reads Claude Code's transcript JSONL, which is not a documented format;
    revisit when a Claude Code release changes it (tests/test_thread.py pins the shape).
    """
    if not line.strip():
        return ""
    d = json.loads(line)
    if not isinstance(d, dict) or d.get("isSidechain"):
        return ""
    if seen is not None and d.get("uuid"):
        if d["uuid"] in seen:
            return ""  # Claude Code sometimes writes a line again; one copy is enough
        seen.add(d["uuid"])
    if own and d.get("sessionId") and d["sessionId"] != own:
        return ""
    if d.get("type") == "attachment":
        # whatever arrives while a turn is running is delivered as a queued attachment: the
        # user's own words, a subagent's notice or report
        att = d.get("attachment")
        prompt = att.get("prompt") if isinstance(att, dict) and att.get("type") == "queued_command" else None
        if not isinstance(prompt, str):
            return ""
        d = {**d, "type": "user", "message": {"content": prompt}}
    if d.get("type") not in ("user", "assistant"):
        return ""
    ts, sid, role = "".join(str(d.get("timestamp") or "").split()) or now(), d.get("sessionId"), d["type"]
    if since and d.get("timestamp") and ts[:19] <= since[:19]:
        return ""
    content = (d.get("message") or {}).get("content")
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    out = []
    for b in content or []:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text":
            text = b.get("text", "")
            text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
            start, kind = text.lstrip(), role
            if role == "user":  # not everything on a user line was said by the user
                if d.get("isCompactSummary"):
                    kind = "compaction"  # Claude Code's own summary at a compaction
                elif start.startswith(REPORT):
                    kind = "subagent"  # a report handed back by another agent
                elif start.startswith("<task-notification>"):
                    kind = "subagent" if "<subagent_tokens>" in text else "notification"
                elif d.get("isMeta"):
                    continue  # injected by Claude Code: skill bodies, reminders
            out.append(entry(ts, sid, kind, text))
        elif t == "thinking":
            if b.get("thinking"):
                out.append(entry(ts, sid, "thinking", b["thinking"]))
        elif t == "tool_use":  # the id in the header ties a result to its call
            name = "_".join(str(b.get("name", "")).split()) or "tool"
            out.append(entry(ts, sid, "tool_use", tool_input(b.get("input")),
                             f"{name} {'_'.join(str(b.get('id') or '-').split())}"))
        elif t == "tool_result":
            out.append(entry(ts, sid, "tool_result", flat(b.get("content")),
                             "_".join(str(b.get("tool_use_id") or "-").split())))
        else:
            out.append(entry(ts, sid, role, f"[{t}]"))  # images and other binary blocks
    return "".join(out)


LOCK_STALE = 5  # seconds; a capture takes well under one, so an older lock belongs to a dead process
_held = set()


@contextlib.contextmanager
def locked(sid):
    """One process at a time reads a session's offset, appends and saves the offset: without this,
    parallel `thread` commands store the same transcript lines several times."""
    p = state_path(sid)
    if not p or sid in _held:
        yield
        return
    lock = p.with_suffix(".lock")
    home().mkdir(parents=True, exist_ok=True, mode=0o700)
    lock.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
            break
        except (FileExistsError, PermissionError):  # PermissionError: Windows, while it is being deleted
            try:
                if time.time() - lock.stat().st_mtime > LOCK_STALE:
                    os.unlink(lock)  # its holder died; two waiters doing this at once is the rare leftover race
                    continue
            except OSError:
                continue
            time.sleep(0.02)
    _held.add(sid)
    try:
        yield
    finally:
        _held.discard(sid)
        with contextlib.suppress(OSError):
            os.unlink(lock)


def capture(sid, tpath=None):
    """Append the uncaptured part of the session transcript to the session's active thread.
    Returns the number of transcript lines that produced entries."""
    with locked(sid):
        return _capture(sid, tpath)


def _capture(sid, tpath):
    st = state(sid)
    if not st:
        return 0
    was = st.get("thread")
    tid = st["thread"] = bound(st)  # None also when it was closed or removed by another session
    if isinstance(was, str) and not tid:
        st["lost"] = was  # kept until the session's next command has said so (see target)
    tpath = tpath or find_transcript(sid)
    if tpath and os.path.exists(tpath):
        with open(tpath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if lines and not lines[-1].endswith("\n"):
            lines.pop()  # half-written line; take it next time
        first = st.get("offset", 0)
        if not isinstance(first, int) or not 0 <= first <= len(lines):
            first = 0  # the transcript was replaced by a shorter one, or the state is damaged
        parts, seen = [], set()
        for n, line in enumerate(lines[first:] if tid else [], first + 1):
            try:
                parts.append(render(line, sid, st.get("since"), seen))
            except Exception as e:  # an unknown line shape must not block the lines after it
                parts.append(entry(now(), sid, "event",
                                   f"capture skipped transcript line {n}: {type(e).__name__}"))
        parts = [x for x in parts if x]
        if parts:
            append(tid, "".join(parts))
        st["offset"] = len(lines)  # with no thread (detached) the lines are skipped for good
        write(state_path(sid), json.dumps(st))
        return len(parts)
    write(state_path(sid), json.dumps(st))
    return 0


def detach(sid):
    with locked(sid):
        st = state(sid)
        if st:
            st["thread"] = None
            st.pop("lost", None)
            write(state_path(sid), json.dumps(st))


def bind(sid, tid, backfill=False):
    """Make tid the session's active thread. The transcript so far goes to the previous thread.
    A session that never had a thread is captured from its start only with backfill (`thread new`);
    otherwise capture starts here. Returns the number of backfilled transcript lines."""
    if not state_path(sid):
        print("(no Claude Code session id: nothing bound, nothing will be captured)")
        return 0
    with locked(sid):  # the whole switch, so a hook cannot capture in the middle of it
        st = state(sid) or {"offset": 0, "fresh": True}
        fresh = st.pop("fresh", False)  # never bound: no state yet, or a fork marked by the hook
        if fresh and backfill:
            st["offset"] = 0
        else:
            write(state_path(sid), json.dumps(st))
            capture(sid)  # to the previous thread; with none, this skips what came before
            st = state(sid)
            if not find_transcript(sid):
                # no transcript in reach to skip: a later hook, which is given its path, must not
                # go back before this second
                st["since"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 1))
        st["thread"], st["gen"] = tid, generation(tid)
        st.pop("lost", None)
        write(state_path(sid), json.dumps(st))
        n = capture(sid)
        return n if fresh and backfill else 0


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
        st = state(session_id()) or {}
        was = st.get("lost") or st.get("thread")  # "lost": a hook's capture cleared the binding first
        if isinstance(was, str):
            detach(session_id())  # said once; from here on the session is simply unbound
            die(f"thread {was} was closed or removed by another session, so this session is no longer "
                f"captured: `thread open {was}` (or `thread reopen {was}`) to continue, or pass -t <id>")
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


def by_type(since):
    """What a list of entries is made of, most frequent entry type first: `3 tool_use, 1 note`."""
    n = {}
    for e in since:
        n[e[3]] = n.get(e[3], 0) + 1
    return ", ".join(f"{v} {k}" for k, v in sorted(n.items(), key=lambda kv: -kv[1]))


def activity(tid):
    """Time of the last write to the thread's log; 0 when it has none."""
    log = home() / tid / "log.txt"
    return log.stat().st_mtime if log.exists() else 0


def show_cmd(tid, n, cur):
    """The command that prints log line n of tid whole; it names the thread unless that is the
    caller's active thread, so the hint as printed never shows a line of another thread."""
    return f"thread show {'' if tid == cur else f'-t {tid} '}{n}"


def show(tid, cur=None):
    m = meta(tid)
    print(printable(f"# {m['title']}  [{tid}]  kind={m['kind'] or '-'}  status={m['status']}") + "\n")
    print(printable(summary(tid).strip()) or "(no checkpoint yet)")
    since = since_checkpoint(tid)
    if not since:
        if summary(tid).strip():
            print("\n-- 0 entries since the last checkpoint: the summary is current. --")
        return
    notes = [e for e in since if e[3] == "note"]
    msgs = [e for e in since if e[3] in ("user", "assistant")][-6:]
    text = printable("\n".join(
        f"[{e[1]} {e[3]}] {e[5][:600]}{f'… [clipped; {show_cmd(tid, e[0], cur)}]' if len(e[5]) > 600 else ''}"
        for e in sorted(notes + msgs)))
    if len(text) > CAP:
        text = "…" + text[-CAP:]
    print(f"\n-- {len(since)} entries since the last checkpoint ({by_type(since)}); "
          f"notes and latest messages: --")
    print(text)
    print("-- `thread grep <regex>` for more; `thread checkpoint` once caught up --")


def cmd_new(a):
    title = printable(" ".join(" ".join(a.title).split()))  # one line, single spaces
    if not title:
        die("empty title")
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50].strip("-") or "thread"
    tid, n = base, 1
    while (home() / tid).exists():
        n += 1
        tid = f"{base}-{n}"
    save_meta({"id": tid, "title": title, "kind": printable(" ".join((a.kind or "").split())), "status": "open",
               "created": now(), "cwd": os.path.realpath(os.getcwd()), "uid": os.urandom(4).hex()})
    sid = session_id()
    was = active(sid)
    n = bind(sid, tid, backfill=True)
    append(tid, entry(now(), sid, "event", f"created: {title}"))
    print(f"created thread {tid}"
          + (f"; this session is now captured into it, no longer into {was}" if was else "")
          + (f"; {n} earlier transcript lines of this session were captured into it" if n else ""))


def recover(tid, sid):
    """Capture the uncaptured tail of other sessions bound to tid whose transcript is still on
    disk: a session that was interrupted and then archived got no hook for its last turn."""
    for p in sorted((home() / ".sessions").glob("*.json")):
        other = p.stem
        if other == sid or bound(state(other)) != tid or not find_transcript(other):
            continue
        try:
            n = capture(other)  # under that session's lock and id; its offset advances
        except Exception as e:
            print(f"thread: could not check session {other[:8]} for uncaptured work ({type(e).__name__})",
                  file=sys.stderr)
            continue
        if n:
            print(f"recovered {n} transcript lines from session {other[:8]} that ended without a capture "
                  f"(or is still running); they are at the end of the log, after later entries\n")


def cmd_open(a):
    tid = resolve(a.id)
    sid = session_id()
    recover(tid, sid)
    # after this command the thread is the caller's active one only if it is open and can be bound
    show(tid, tid if is_open(tid) and state_path(sid) else None)
    if meta(tid)["status"] == "closed":
        print(f"\n(closed: shown read-only, not bound; `thread reopen {tid}` to work on it again)")
    else:
        bind(sid, tid)


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
    since = since_checkpoint(tid)
    print(f"noted in {tid} ({len(since)} entries since the last checkpoint: {by_type(since)})")


def cmd_checkpoint(a, close=False):
    tid, text, sid = target(a), read_text(a.text), session_id()
    if not is_open(tid):
        die(f"thread {tid} is closed; only notes can be added. `thread reopen {tid}` first")
    try_capture(sid)
    if close:
        recover(tid, sid)  # before the close: afterwards those sessions are of an earlier generation
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
    st = state(sid) or {}
    if not (st.get("thread") or st.get("lost")):  # also clears a binding to a thread closed elsewhere
        die("no active thread")
    capture(sid)
    detach(sid)
    print("detached: this session is no longer captured")


def clip(line, start=0, n=None):
    """At most 400 characters of a log line; `n` is the command that prints the whole entry."""
    line = printable(line)
    if len(line) <= 400:
        return line
    s = max(0, start - 150)
    return ("…" if s else "") + line[s:s + 400] + "…" + (f" [clipped; {n}]" if n else "")


def cmd_show(a):
    tid = target(a)
    p = home() / tid / "log.txt"
    # splitlines, as in cmd_grep: the line numbers are the ones grep prints
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []
    start = a.line - 1
    if not 0 <= start < len(lines):
        die(f"no line {a.line} in the log of {tid}: it has {len(lines)} lines")
    while start >= 0 and not HDR.match(lines[start]):
        start -= 1
    if start < 0:
        die(f"line {a.line} of the log of {tid} is not inside an entry")
    end = start + 1
    while end < len(lines) and not HDR.match(lines[end]):
        end += 1
    print(printable(f"{tid}:{start + 1}  " + "\n".join(lines[start:end])))


def cmd_grep(a):
    try:
        rx = re.compile(a.pattern, re.I)
    except re.error as e:
        die(f"bad regex: {e}")
    if a.all and a.thread:
        die("use --all or -t, not both")
    if a.offset <= 0:
        try_capture(session_id())  # page 1 sees the turn in progress; later pages need a stable log
    types = {t for t in (a.type or "").replace(",", " ").split()}
    if types - set(TYPES):
        die(f"unknown entry type {', '.join(sorted(types - set(TYPES)))}; the types are {', '.join(TYPES)}")
    ctx = min(max(a.context, 0), 3)
    cur = active(session_id())
    hits = []  # (entry time, thread, entry line, line, header, {line: text} with context)
    by_type, by_thread = {}, {}
    for tid in (all_ids() if a.all else [target(a)]):
        p = home() / tid / "log.txt"
        if not p.exists():
            continue
        # shortcut: reads the whole log into memory; stream it if logs reach hundreds of MB
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        heads = [bool(HDR.match(l)) for l in lines]
        head, start, kind, skip, calls, own_ids = "", 0, "", False, {}, set()
        for i, line in enumerate(lines):
            if heads[i]:
                f = line.split()
                head, start, kind = printable(line), i, f[3]
                skip = bool(types) and kind not in types
                # the call id: `tool_use <name> <id>` or `tool_result <id>`; "-" when it had none
                cid = f[-2] if len(f) == (7 if kind == "tool_use" else 6) and f[-2] != "-" else None
                if kind == "tool_use" and cid:
                    j = i + 1
                    while j < len(lines) and not heads[j]:
                        j += 1
                    c = next((n for n in range(i + 1, j) if lines[n].startswith("command: ")), None)
                    calls[cid] = f"{f[4]}: {clip(lines[c if c else i + 1] if j > i + 1 else '')[:160]}"
                    # an earlier `thread grep` call holds its own pattern, and its result repeats
                    # the log: searching them would make the match count grow with every page
                    if c and f[4] in ("Bash", "PowerShell") and runs_grep("\n".join(lines[c:j])[9:]):
                        own_ids.add(cid)
                if kind in ("tool_use", "tool_result") and cid in own_ids:
                    skip = True
                if kind == "tool_result" and cid in calls:
                    head = f"{head}  <- {calls[cid]}"  # which call printed this
            m = None if skip else rx.search(line)
            if not m:
                continue
            by_type[kind] = by_type.get(kind, 0) + 1
            by_thread[tid] = by_thread.get(tid, 0) + 1
            if a.count:
                continue
            lo = hi = i  # context stays inside the entry: a neighbour's text is not this match's
            while i - lo < ctx and lo > start + 1:
                lo -= 1
            while hi - i < ctx and hi + 1 < len(lines) and not heads[hi + 1]:
                hi += 1
            near = {j + 1: clip(lines[j], m.start() if j == i else 0, show_cmd(tid, j + 1, cur)) for j in range(lo, hi + 1) if j > start}
            hits.append((head.split()[1][:19] if head else "", tid, start + 1, i + 1, head, near))
    total = sum(by_type.values())
    spread = lambda d: ", ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda kv: -kv[1]))
    extra = ([f"[by type: {spread(by_type)}]"] if len(by_type) > 1 else []) + \
            ([f"[by thread: {spread(by_thread)}]"] if a.all and by_thread else [])
    if a.count:
        print("\n".join([str(total)] + extra))
        return
    # newest entry first (a later decision replaces an earlier one); inside an entry, top to bottom
    hits.sort(key=lambda h: (h[0], h[1], h[2]), reverse=not a.oldest)
    hits = [h for _, group in _grouped(hits) for h in sorted(group, key=lambda h: h[3])]
    first, size = max(a.offset, 0), min(max(a.max, 1), 30)
    shown, text = 0, ""
    for n in range(1, len(hits[first:first + size]) + 1):
        trial = _page(hits[first:first + n])
        if shown and len(trial) > CAP:
            break  # the page ends early; the footer points at the first match not shown
        shown, text = n, trial
    if text:
        print(text)
    end = first + shown
    more = f"; next page: --offset {end}" if end < total else ""
    print("\n".join([f"[matches {first + 1 if shown else 0}-{end if shown else 0} of {total}{more}]"] + extra))


def _grouped(hits):
    """Consecutive hits of the same entry, as (key, [hits])."""
    out = []
    for h in hits:
        if out and out[-1][0] == h[1:3]:
            out[-1][1].append(h)
        else:
            out.append((h[1:3], [h]))
    return out


def _page(hits):
    """One header per entry, its matching lines in order with merged context (as in the paper)."""
    blocks = []
    for (tid, start), group in _grouped(hits):
        near, marked = {}, {h[3] for h in group}
        for h in group:
            near.update(h[5])
        rows, last = [f"{tid}:{start}  {group[0][4]}"], None
        for n in sorted(near):
            if last is not None and n > last + 1:
                rows.append("  --")
            rows.append(f"{'>' if n in marked else ' '} {n}: {near[n]}")
            last = n
        blocks.append("\n".join(rows))
    return "\n--\n".join(blocks)


def cmd_list(a):
    cur = active(session_id())
    rows = []
    for tid in all_ids():
        try:
            m = meta(tid)
            if (m["status"] == "open" or a.all) and (not a.kind or m["kind"] == a.kind):
                t = activity(tid)  # shown in UTC, as the log and meta.json are
                rows.append((t, printable(f"{'*' if tid == cur else ' '} {tid}  {m['kind'] or '-'}  {m['status']}"
                                          f"  {time.strftime('%Y-%m-%d', time.gmtime(t))}  {m['title']}")))
        except (OSError, ValueError, KeyError, TypeError):
            continue  # unreadable meta.json: leave it out rather than fail the listing
    print("\n".join(r for _, r in sorted(rows, reverse=True)) or "(no threads)")
    if rows:
        print("(dates: last log activity, UTC)")
    if (home() / "errors.log").exists():
        print(f"(hook errors are recorded in {home() / 'errors.log'})")


def cmd_export(a):
    tid = resolve(a.id)
    m = meta(tid)
    print(printable(f"# {m['title']}\n\n`{tid}` · kind: {m['kind'] or '-'} · status: {m['status']} · "
                    f"created: {m.get('created')}\n\n## Summary\n\n{summary(tid).strip() or '(none)'}\n\n## Notes\n"))
    for e in entries(tid):
        if e[3] == "note":
            print(printable(f"- {e[1]}: {e[5]}"))


def cmd_hook(a):
    """Claude Code hook entry point. Never fails the session: errors go to errors.log."""
    try:
        raw = sys.stdin.read().lstrip("\ufeff")  # PowerShell may put a byte-order mark first
        if not raw.strip():
            return  # run by hand with nothing on stdin
        d = json.loads(raw)
        sid = d.get("session_id") or ""
        if not state_path(sid):
            return
        start = d.get("hook_event_name") == "SessionStart"
        if start and d.get("source") == "fork" and not state(sid):
            # the fork's transcript begins with a copy of its parent's lines: mark where it starts
            write(state_path(sid), json.dumps({"offset": 0, "thread": None, "fresh": True, "since": now()}))
        capture(sid, d.get("transcript_path"))
        tid = active(sid)
        if not start or d.get("agent_id"):
            return  # only a session start of the main agent prints anything
        if tid and d.get("source") == "compact":
            text, since = printable(summary(tid).strip()), since_checkpoint(tid)
            print(f"Active thread: {tid} ({meta(tid)['title']}). Details lost to compaction are in "
                  f"its log: run `thread grep <regex>` before re-deriving anything.\n\n"
                  # Claude Code keeps only a preview of hook output above 10,000 characters
                  f"Thread summary:\n{text[:CAP] or '(no checkpoint yet)'}"
                  + (f"\n…[cut at {CAP} characters; `thread open {tid}` prints all of it]"
                     if len(text) > CAP else "")
                  + (f"\n\n{len(since)} entries{' (' + by_type(since) + ')' if since else ''} were logged "
                     f"after this summary, so it may be out of date: "
                     f"write a fresh `thread checkpoint` now." if since or not text else ""))
        elif tid:
            print(printable(f"Active thread: {tid} ({meta(tid)['title']}). This session is captured into it."))
        else:
            norm = lambda path: os.path.normcase(os.path.realpath(path)).rstrip(os.sep)
            is_root = lambda path: os.path.dirname(path + os.sep) == path + os.sep  # "" is "/"
            here, near = norm(d.get("cwd") or os.getcwd()), []
            for t in all_ids():
                try:
                    m = meta(t)
                    c = norm(m["cwd"]) if m.get("cwd") else None
                    # the same folder, or one of the two inside the other (a thread is often started
                    # after the shell moved into a subfolder). A root folder on either side would
                    # match everything, so it matches nothing.
                    if m["status"] == "open" and c is not None and not is_root(c) and not is_root(here) and \
                            (here == c or here.startswith(c + os.sep) or c.startswith(here + os.sep)):
                        near.append((activity(t), t))
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            if near:
                near = [t for _, t in sorted(near, reverse=True)]  # most recent log activity first
                more = f" (and {len(near) - 8} more: `thread list`)" if len(near) > 8 else ""
                print(f"Open threads for this folder: {', '.join(near[:8])}{more}. None is active, so "
                      f"this session is not captured. Open one only if you are asked to continue that "
                      f"work (`thread open <id>`).")
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
    s.add_argument("--type", help="search only these entry types, e.g. user,assistant,note")
    s.add_argument("--oldest", action="store_true", help="list the oldest matches first")
    s = cmd("show", cmd_show, "print the whole log entry that contains a log line number", thread=True)
    s.add_argument("line", type=int, help="a line number, as `thread grep` and `thread open` print them")
    s = cmd("list", cmd_list, "list open threads")
    s.add_argument("--all", action="store_true", help="include closed threads")
    s.add_argument("--kind")
    cmd("export", cmd_export, "print the summary and all notes as markdown").add_argument("id")
    cmd("hook", cmd_hook, "Claude Code hook entry point (reads the hook JSON on stdin)")

    for s in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):  # Windows pipes default to the locale code page
            s.reconfigure(encoding="utf-8", errors="replace")
    a = p.parse_args(argv)
    try:
        a.fn(a)
    except ValueError as e:  # a damaged meta.json; the hook has its own handler and never gets here
        die(f"{e}: repair or remove the file under {home()}")


if __name__ == "__main__":
    main()
