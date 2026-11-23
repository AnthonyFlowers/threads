import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import thread  # noqa: E402

SID = "sess-1"


def msg(role, content, **kw):
    return json.dumps({"type": role, "sessionId": SID, "timestamp": "2026-01-01T00:00:00.000Z",
                       "message": {"content": content}, **kw}) + "\n"


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.transcript = root / "claude" / "projects" / "p" / f"{SID}.jsonl"
        self.transcript.parent.mkdir(parents=True)
        self.transcript.write_text("")
        # HOME too: if the code under test ever ignored THREADS_HOME, it must still not reach the real home
        self.env = {"THREADS_HOME": str(root / "threads"), "CLAUDE_CONFIG_DIR": str(root / "claude"),
                    "CLAUDE_CODE_SESSION_ID": SID, "HOME": str(root / "home"), "USERPROFILE": str(root / "home")}
        self.old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)

    def tearDown(self):
        for k, v in self.old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.tmp.cleanup()

    def say(self, *lines):
        with open(self.transcript, "a") as f:
            f.writelines(lines)

    def run_cli(self, *argv, stdin=""):
        out, old = io.StringIO(), sys.stdin
        sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out):
                thread.main(list(argv))
        finally:
            sys.stdin = old
        return out.getvalue()

    def hook(self, event="Stop", source="compact", **more):
        sid = os.environ.get("CLAUDE_CODE_SESSION_ID", SID)
        return self.run_cli("hook", stdin=json.dumps(
            {"session_id": sid, "transcript_path": str(self.transcript.with_name(f"{sid}.jsonl")),
             "hook_event_name": event, **({"source": source} if event == "SessionStart" else {}), **more}))

    def log(self, tid):
        return (thread.home() / tid / "log.txt").read_text(encoding="utf-8")

    def test_backfill_capture_and_switch(self):
        self.say(msg("user", "before any thread"))
        self.run_cli("new", "Fix", "Login!", "--kind", "bug")
        self.assertIn("before any thread", self.log("fix-login"))  # backfilled from session start
        self.say(msg("assistant", [
            {"type": "text", "text": "looking"},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            {"type": "image"}]),
            msg("user", [{"type": "tool_result", "content": [{"type": "text", "text": "x" * 9000}]}]),
            msg("assistant", "sidechain", isSidechain=True))
        self.hook()
        self.hook()  # second run must not duplicate
        log = self.log("fix-login")
        self.assertEqual(log.count("looking"), 1)
        self.assertIn("tool_use Bash - ===\ncommand: ls\n", log)
        self.assertIn("x" * 9000, log)  # lossless: nothing truncated
        self.assertIn("[image]", log)
        self.assertNotIn("sidechain", log)

        self.say(msg("user", "still about login"))
        self.run_cli("new", "Other")
        self.say(msg("user", "about other"))
        self.hook()
        self.assertIn("still about login", self.log("fix-login"))
        self.assertNotIn("about other", self.log("fix-login"))
        self.assertIn("about other", self.log("other"))
        self.assertNotIn("still about login", self.log("other"))

    def test_detach_skips_then_rebinding_does_not_backfill(self):
        self.run_cli("new", "A")
        self.run_cli("detach")
        self.say(msg("user", "secret stuff"))
        self.hook()
        self.run_cli("open", "a")
        self.say(msg("user", "back on a"))
        self.hook()
        self.assertNotIn("secret stuff", self.log("a"))
        self.assertIn("back on a", self.log("a"))

    def test_checkpoint_stale_tail_close_reopen(self):
        self.run_cli("new", "A")
        with self.assertRaises(SystemExit):
            self.run_cli("close", stdin="  ")  # close needs a final summary
        self.run_cli("checkpoint", stdin="State: halfway\n")
        self.run_cli("note", "found", "the", "cause")
        self.say(msg("user", "later message"))
        self.hook()
        out = self.run_cli("open", "a")
        self.assertIn("State: halfway", out)
        self.assertIn("2 entries since the last checkpoint", out)
        self.assertIn("found the cause", out)
        self.assertIn("later message", out)

        self.run_cli("close", "done: fixed")
        self.assertEqual(thread.meta("a")["status"], "closed")
        self.assertIsNone(thread.active(SID))
        self.assertIn("(no threads)", self.run_cli("list"))
        self.assertIn("read-only", self.run_cli("open", "a"))
        self.assertIsNone(thread.active(SID))  # opening a closed thread does not bind
        self.run_cli("reopen", "a")
        self.assertEqual(thread.active(SID), "a")
        self.assertIn("found the cause", self.run_cli("export", "a"))

    def test_grep_paging_count_all(self):
        self.run_cli("new", "A")
        for i in range(12):
            self.run_cli("note", f"Needle {i}")
        self.run_cli("note", "=== looks like a header ===")
        self.assertEqual(self.run_cli("grep", "needle", "--count").strip(), "12")
        page = self.run_cli("grep", "needle")
        self.assertIn("[matches 1-10 of 12; next page: --offset 10]", page)
        self.assertIn("[matches 11-12 of 12]", self.run_cli("grep", "needle", "--offset", "10"))
        self.assertEqual(sum(1 for e in thread.entries("a") if e[3] == "note"), 13)  # fake header escaped
        self.run_cli("new", "B")
        self.assertEqual(self.run_cli("grep", "needle", "--count").strip(), "0")
        self.assertEqual(self.run_cli("grep", "needle", "--count", "--all"), "12\n[by thread: a 12]\n")
        self.assertLessEqual(len(self.run_cli("grep", ".", "--all", "--max", "30")), thread.CAP + 200)

    def test_hook_reinjects_after_compaction_and_never_raises(self):
        self.assertEqual(self.hook("SessionStart"), "")  # unbound session: silent
        self.run_cli("new", "A")
        self.run_cli("checkpoint", "Goal: x")
        out = self.hook("SessionStart")
        self.assertIn("Goal: x", out)
        self.assertIn("thread grep", out)
        self.run_cli("hook", stdin="not json")  # logged, not raised
        self.assertTrue((thread.home() / "errors.log").exists())


    def test_bad_transcript_line_does_not_stop_capture(self):
        self.run_cli("new", "A")
        self.say(json.dumps({"type": "user", "sessionId": SID, "message": "plain string"}) + "\n",
                 msg("user", [{"type": "tool_result", "content": 7}]),
                 msg("user", "cut \ud83d here"),
                 msg("user", "after the bad lines"))
        self.hook()
        self.assertFalse((thread.home() / "errors.log").exists())
        log = self.log("a")
        self.assertIn("capture skipped transcript line", log)
        self.assertIn("after the bad lines", log)
        self.run_cli("note", "still works")

    def test_grep_cap_ends_page_early_and_footer_is_true(self):
        self.run_cli("new", "A")
        for i in range(12):
            self.run_cli("note", stdin=f"{'x' * 500}\nneedle {i}\n{'y' * 500}\n")
        seen, offset = [], 0
        while True:
            page = self.run_cli("grep", "needle", "--offset", str(offset))
            self.assertLessEqual(len(page), thread.CAP + 200)
            seen += [re.sub(r"^> \d+: ", "> ", l) for l in page.splitlines() if l.startswith("> ")]
            nxt = page.rsplit("--offset ", 1)
            if len(nxt) == 1:
                break
            offset = int(nxt[1].rstrip("]\n"))
        self.assertEqual(seen, [f"> needle {i}" for i in reversed(range(12))])  # every match, newest first
        self.assertIn("[matches 0-0 of 12]", self.run_cli("grep", "needle", "--offset", "99"))
        self.assertIn("[matches 1-", self.run_cli("grep", "needle", "--offset", "-5"))

    def test_close_from_another_session_stops_capture(self):
        self.run_cli("new", "A")
        os.environ["CLAUDE_CODE_SESSION_ID"] = "sess-2"
        self.run_cli("close", "-t", "a", "Outcome: done")
        os.environ["CLAUDE_CODE_SESSION_ID"] = SID
        self.assertIsNone(thread.active(SID))
        self.say(msg("user", "after close"))
        self.hook()
        self.assertNotIn("after close", self.log("a"))
        self.assertNotIn("entries since", self.run_cli("open", "a"))  # events do not count

    def test_note_text_with_flags_modes_and_no_session(self):
        self.run_cli("new", "A")
        self.run_cli("note", "use", "--max", "30", "or", "-t", "x")
        self.assertIn("use --max 30 or -t x", self.log("a"))
        with self.assertRaises(SystemExit):
            self.run_cli("new", "  ")
        if os.name == "posix":
            mode = lambda p: p.stat().st_mode & 0o777
            self.assertEqual(mode(thread.home()), 0o700)
            self.assertEqual(mode(thread.home() / "a" / "log.txt"), 0o600)
            self.run_cli("hook", stdin="not json")
            self.assertEqual(mode(thread.home() / "errors.log"), 0o600)
        del os.environ["CLAUDE_CODE_SESSION_ID"]
        self.assertIn("nothing bound", self.run_cli("new", "B"))
        self.run_cli("note", "-t", "b", "by hand")
        self.assertIn("by hand", self.log("b"))
        with self.assertRaises(SystemExit):
            self.run_cli("note", "no thread")


    def as_session(self, sid):
        os.environ["CLAUDE_CODE_SESSION_ID"] = sid

    def test_grep_paging_survives_capture_of_its_own_calls(self):
        self.run_cli("new", "zzz")
        for i in range(25):
            self.run_cli("note", f"needle item{i:03d}")
        self.run_cli("new", "aaa")  # the active thread sorts before the one holding the matches
        seen, offset, pages = [], 0, 0
        while pages < 10:
            pages += 1
            page = self.run_cli("grep", "needle item", "--all", "--offset", str(offset))
            seen += re.findall(r"^> \d+: (needle item\d+)$", page, re.M)
            # the call and its output land in the transcript, and a hook captures them
            self.say(msg("assistant", [{"type": "tool_use", "id": f"t{pages}", "name": "Bash", "input":
                         {"command": f'thread grep "needle item" --all --offset {offset}'}}]),
                     msg("user", [{"type": "tool_result", "tool_use_id": f"t{pages}", "content": page}]))
            self.hook()
            nxt = re.search(r"--offset (\d+)\]", page)
            if not nxt:
                break
            offset = int(nxt[1])
        self.assertEqual(seen, [f"needle item{i:03d}" for i in reversed(range(25))])
        self.assertLess(pages, 10)  # the footer stops offering pages
        self.assertRegex(self.log("aaa"), r"> \d+: needle item000")  # calls and output are logged, not searched

    def test_only_new_backfills_and_a_fork_starts_at_the_fork(self):
        self.say(msg("user", "parent line"))
        self.run_cli("new", "A")
        # a second session: lines of another session's id, then its own; `open` captures from now on
        other = self.transcript.with_name("sess-2.jsonl")
        other.write_text(self.transcript.read_text() + msg("user", "before open").replace(SID, "sess-2"))
        self.as_session("sess-2")
        self.run_cli("open", "a")
        with open(other, "a") as f:
            f.write(msg("user", "after open").replace(SID, "sess-2"))
        self.hook()
        log = self.log("a")
        self.assertEqual(log.count("parent line"), 1)
        self.assertNotIn("before open", log)
        self.assertIn("after open", log)
        # a fork: its file starts with the parent's lines under the fork's own id and old timestamps
        fork = self.transcript.with_name("sess-3.jsonl")
        fork.write_text(msg("user", "copied from the parent").replace(SID, "sess-3"))
        self.as_session("sess-3")
        self.assertIn("None is active", self.hook("SessionStart", source="fork"))
        with open(fork, "a") as f:
            f.write(msg("user", "said in the fork").replace(SID, "sess-3").replace("2026-01-01", "2099-01-01"))
        self.assertIn("1 earlier transcript lines", self.run_cli("new", "Forked work"))
        self.assertNotIn("copied from the parent", self.log("forked-work"))
        self.assertIn("said in the fork", self.log("forked-work"))

    def test_session_start_reminder_type_filter_and_readable_tool_calls(self):
        self.run_cli("new", "A")
        here = os.getcwd()
        self.as_session("sess-2")
        start = lambda **kw: self.hook("SessionStart", **kw)
        self.assertIn("Open threads started in this folder: a. None is active", start(source="startup", cwd=here))
        self.assertIn("a. None is active", start(source="clear", cwd=os.path.join(here, "sub")))
        self.assertEqual(start(source="startup", cwd=os.path.dirname(here) or "/nowhere"), "")
        self.assertEqual(start(source="startup", cwd=here, agent_id="x"), "")  # a subagent's start
        self.as_session(SID)
        self.assertEqual(start(source="resume", cwd=here), "Active thread: a (A). This session is captured into it.\n")
        self.assertEqual(self.hook("Stop", cwd=here), "")
        cmd = 'pytest -k "batch and not slow" C:\\work\\app\\batch.py\necho done'
        self.say(msg("user", "we decided to keep batch size 50"),
                 msg("assistant", [{"type": "tool_use", "id": "t1", "name": "Bash",
                                    "input": {"command": cmd, "timeout": 5}}]),
                 msg("user", [{"type": "tool_result", "tool_use_id": "t1", "content": "def batch_50(): pass"}]))
        self.hook()
        self.assertIn(" tool_use Bash t1 ===\ncommand: " + cmd + "\ntimeout: 5\n", self.log("a"))
        hit = self.run_cli("grep", 'pytest -k "batch', "--context", "0")
        self.assertIn(" tool_use Bash t1 ===", hit)  # the command is found as typed
        self.assertIn("[matches 1-1 of 1]", self.run_cli("grep", r"C:\\work\\app\\batch\.py"))
        self.assertEqual(self.run_cli("grep", "batch", "--count"),
                         "3\n[by type: user 1, tool_use 1, tool_result 1]\n")
        self.assertIn(" tool_result t1 ===  <- Bash: command: pytest -k", self.run_cli("grep", "def batch_50"))
        self.assertEqual(self.run_cli("grep", "batch", "--count", "--type", "user,note").strip(), "1")
        self.assertRegex(self.run_cli("grep", "batch", "--type", "user"), r"\n> \d+: we decided")
        older = self.run_cli("grep", "batch", "--oldest", "--context", "0")
        self.assertLess(older.index("we decided"), older.index("def batch_50"))
        self.assertIn("[by type: ", older)
        # newest first, across threads
        self.run_cli("new", "B")
        self.run_cli("note", "batch again, later, in another thread")
        page = self.run_cli("grep", "batch", "--all", "--context", "0")
        self.assertLess(page.index("batch again"), page.index("def batch_50"))
        self.assertLess(page.index("def batch_50"), page.index("we decided"))

    def test_closed_thread_accepts_notes_only_and_stale_binding_clears(self):
        self.run_cli("new", "A")
        self.as_session("sess-2")
        self.run_cli("close", "-t", "a", "Outcome: done")
        for cmd in ("checkpoint", "close"):
            with self.assertRaises(SystemExit):
                self.run_cli(cmd, "-t", "a", "overwrite")
        self.assertIn("Outcome: done", thread.summary("a"))
        self.run_cli("note", "-t", "a", "late remark")
        self.assertIn("late remark", self.log("a"))
        self.as_session(SID)
        self.run_cli("detach")  # bound to a thread closed elsewhere: detach still clears it
        self.assertIsNone(thread.state(SID)["thread"])
        # lines written while closed stay out, even when the same session reopens it
        self.as_session("sess-2")
        self.run_cli("open", "a")
        self.as_session(SID)
        self.run_cli("new", "B")
        self.as_session("sess-2")
        self.run_cli("close", "-t", "b", "Outcome: done")
        self.as_session(SID)
        self.say(msg("user", "while b was closed"))
        self.run_cli("reopen", "b")
        self.assertNotIn("while b was closed", self.log("b"))

    def test_close_of_another_thread_keeps_binding_and_ids_resolve(self):
        self.run_cli("new", "Alpha one")
        self.run_cli("new", "Alpha one")  # same title: suffixed id
        self.assertTrue((thread.home() / "alpha-one-2").is_dir())
        self.run_cli("new", "Beta", "--kind", "bug")
        self.run_cli("close", "-t", "alpha-one-2", "Outcome: done")
        self.assertEqual(thread.active(SID), "beta")
        self.run_cli("note", "--", "--starts with a dash")
        self.assertIn("\n--starts with a dash\n", self.log("beta"))
        self.assertIn("Beta", self.run_cli("open", "be"))  # unique prefix
        with self.assertRaises(SystemExit):
            self.run_cli("open", "al")  # ambiguous prefix
        listed = self.run_cli("list", "--kind", "bug")
        self.assertIn("beta", listed)
        self.assertNotIn("alpha", listed)
        self.run_cli("checkpoint", "Goal: beta")
        out = self.run_cli("export", "beta")
        self.assertIn("--starts with a dash", out)
        self.assertNotIn("created: Beta", out)  # notes only, no other entries
        self.assertIsNone(thread.state_path("../evil"))

    def test_half_written_line_blank_line_and_invalid_json(self):
        self.run_cli("new", "A")
        whole = msg("user", "complete at last")
        self.say("\n", "{not json\n", whole[:-20])
        self.hook()
        self.assertNotIn("complete at last", self.log("a"))
        self.assertEqual(self.log("a").count("capture skipped transcript line"), 1)
        self.say(whole[-20:])
        self.hook()
        self.assertEqual(self.log("a").count("complete at last"), 1)

    def test_grep_flags_are_clamped_and_long_lines_clipped(self):
        self.run_cli("new", "A")
        for i in range(40):
            body = "".join(f"b{n} {i}\n" for n in range(5))
            self.run_cli("note", stdin=f"{body}{'z' * 2000} needle {i} {'z' * 2000}\n{body}")
        page = self.run_cli("grep", "needle", "--max", "99", "--context", "9")
        first = page.split("\n--\n")[0].splitlines()
        self.assertEqual(len(first), 1 + 7)  # location line + match with 3 lines either side
        self.assertEqual([re.sub(r"^  \d+: ", "", l) for l in first[1:4] + first[5:]],
                         [f"b{n} 39" for n in (2, 3, 4, 0, 1, 2)])
        hit = next(l for l in first if l.startswith("> "))
        self.assertIn("needle 39", hit)
        self.assertLess(len(hit), 500)
        self.assertLessEqual(len(re.findall(r"^> ", page, re.M)), 30)
        self.assertEqual(len(re.findall(r"^> ", self.run_cli("grep", "needle", "--max", "0")[:9000], re.M)), 1)

    def test_hook_as_a_process_is_silent_exits_zero_and_caps_the_summary(self):
        self.run_cli("new", "A")
        self.run_cli("checkpoint", stdin="S" * 9000)
        self.say(msg("user", "ünïcödé ✓"))
        script = str(Path(thread.__file__).resolve())

        def hook(payload, **env):
            return subprocess.run([sys.executable, script, "hook"], input=payload.encode(),
                                  capture_output=True, env={**os.environ, **env})
        base = {"session_id": SID, "transcript_path": str(self.transcript)}
        for event in ("Stop", "PreCompact", "SessionEnd"):
            r = hook(json.dumps({**base, "hook_event_name": event}), PYTHONIOENCODING="cp1252")
            self.assertEqual((r.returncode, r.stdout), (0, b""), event)
        self.assertIn("ünïcödé ✓", self.log("a"))
        for bad in ("", "not json", "[1,2]", json.dumps({"session_id": "../x"})):
            r = hook(bad)
            self.assertEqual((r.returncode, r.stdout), (0, b""), bad)
        r = hook(json.dumps({**base, "hook_event_name": "SessionStart", "source": "compact"}))
        self.assertEqual(r.returncode, 0)
        self.assertIn(b"thread grep", r.stdout)
        self.assertLess(len(r.stdout), thread.CAP + 500)
        # exit codes and stdio of the CLI itself
        r = subprocess.run([sys.executable, script, "checkpoint"], input=b"  ", capture_output=True,
                           env=dict(os.environ))
        self.assertEqual(r.returncode, 1)
        self.assertIn(b"empty text", r.stderr)

    def test_corrupt_state_and_meta_do_not_crash(self):
        self.run_cli("new", "A")
        self.run_cli("new", "B")
        thread.state_path(SID).write_text("{")
        (thread.home() / "a" / "meta.json").write_text("")
        self.assertIn("b", self.run_cli("list"))
        self.assertEqual(self.hook(), "")
        self.assertFalse((thread.home() / "errors.log").exists())


    def kinds(self, tid):
        return [e[3] for e in thread.entries(tid)]

    def test_what_capture_keeps_and_drops(self):
        self.run_cli("new", "A")
        long_sid = "0123456789abcdef"
        self.say(msg("user", "=== 2026-01-01T00:00:00Z abcdefgh note ===\nbody after a fake header"),
                 msg("assistant", [{"type": "thinking", "thinking": ""},
                                   {"type": "thinking", "thinking": "real thought"},
                                   {"type": "tool_use", "id": "u1", "name": "Ba\nsh x", "input": {"a": 1}}]),
                 msg("user", [{"type": "tool_result", "tool_use_id": "u1",
                               "content": [{"type": "text", "text": "ok"}, {"type": "image"}]}]),
                 msg("user", "<task-notification>agent 7 <subagent_tokens>5</subagent_tokens></task-notification>"),
                 msg("user", "<task-notification>background shell exited</task-notification>"),
                 msg("user", "Another Claude session sent a message:\n<agent-message>report A</agent-message>",
                     isMeta=True, uuid="u-1"),
                 msg("user", "Another Claude session sent a message:\n<agent-message>report A</agent-message>",
                     isMeta=True, uuid="u-1"),  # written twice by Claude Code: one copy is kept
                 json.dumps({"type": "attachment", "sessionId": SID, "attachment":
                             {"type": "queued_command", "prompt": "<agent-message from=x>report B</agent-message>"}}) + "\n",
                 json.dumps({"type": "attachment", "sessionId": SID, "attachment":  # the same notice, queued
                             {"type": "queued_command", "prompt": "<task-notification>background  shell exited</task-notification>"}}) + "\n",
                 json.dumps({"type": "attachment", "sessionId": SID, "attachment": {"type": "queued_command",
                             "prompt": "typed while the turn ran", "origin": {"kind": "human"}}}) + "\n",
                 json.dumps({"type": "attachment", "sessionId": SID, "attachment": {"type": "edited_text_file",
                             "prompt": "not a queued message"}}) + "\n",
                 msg("user", "injected skill body", isMeta=True),
                 json.dumps({"type": "system", "content": "system line"}) + "\n",
                 json.dumps({"type": "attachment", "attachment": "attached"}) + "\n",
                 json.dumps({"type": "user", "message": {"content": "no session id"}}) + "\n",
                 msg("user", "other id").replace(SID, long_sid))
        self.hook()
        log = self.log("a")
        self.assertEqual(self.kinds("a"), ["event", "user", "thinking", "tool_use", "tool_result", "subagent", "notification", "subagent",
                          "subagent", "notification", "user", "user"])
        # nothing is de-duplicated by text: a notice that arrives queued and as a user line is kept twice
        self.assertEqual((log.count("report A"), log.count("report B"), log.count("shell exited")), (1, 1, 2))
        self.assertIn(" user ===\ntyped while the turn ran\n", log)  # the user's mid-turn message
        self.assertNotIn("not a queued message", log)
        # the same text again, queued or not, in this capture run or a later one, is never dropped
        self.say(json.dumps({"type": "attachment", "sessionId": SID, "attachment":
                             {"type": "queued_command", "prompt": "<agent-message>report C</agent-message>"}}) + "\n")
        self.hook()
        self.say(msg("user", "Another Claude session sent a message:\n<agent-message>report C</agent-message>",
                     isMeta=True),
                 msg("user", "<agent-message>report C</agent-message>"), msg("user", "go on"), msg("user", "go on"))
        self.hook()
        log = self.log("a")
        self.assertEqual(log.count("<agent-message>report C</agent-message>"), 3)
        self.assertEqual(log.count("\ngo on\n"), 2)
        queued = json.dumps({"type": "attachment", "sessionId": SID, "attachment":
                             {"type": "queued_command", "prompt": "yes", "origin": {"kind": "human"}}}) + "\n"
        self.say(queued, msg("user", "yes"))
        self.hook()
        self.say(msg("user", "yes"), msg("user", "yes"))
        self.hook()
        self.assertEqual(self.log("a").count(" user ===\nyes\n"), 4)
        self.assertIn("\n === 2026-01-01T00:00:00Z abcdefgh note ===\n", log)  # escaped, not an entry
        self.assertIn(" tool_use Ba_sh_x u1 ===\na: 1\n=== 2026-01-01T00:00:00.000Z sess-1 tool_result u1 ===", log)
        self.assertIn("ok\n[image]\n", log)
        self.assertIn("no session id", log)
        for dropped in ("injected skill body", "system line", "attached", "other id"):
            self.assertNotIn(dropped, log)
        self.as_session(long_sid)
        self.run_cli("note", "-t", "a", "x")
        self.assertIn(" 01234567 note ===", self.log("a"))
        self.assertNotIn("012345678", self.log("a"))

    def test_grep_call_detection(self):
        hit = ["thread grep x", "cd /r && thread grep x", "python3 thread.py grep x", "./thread.py grep x",
               "THREADS_HOME=/t thread grep x --all", 'py "C:/t/thread.py" grep x', "ls\nthread grep x"]
        miss = ['git commit -m "fix thread grep paging"', 'grep -rn "thread grep" README.md',
                "echo see the thread grep docs", 'thread note "use thread grep later"', "threads grep x"]
        hit += ["timeout 5 thread grep x", "{ thread grep x; }", "! thread grep x",
                "/usr/bin/env python3 ./thread.py grep x", "rtk thread grep foo", "env -u X THREADS_HOME=/tmp/t python3 thread.py grep foo",
                "for t in a b; do thread grep $t; done", "if true; then thread grep x; fi", "time thread grep x",
                "echo `thread grep x`", "ls | xargs thread grep", "uv run thread grep x", "thread grep 'a|b' --count"]
        miss += ["thread grep-like x", "git commit -m 'docs; thread grep is skipped'", "git commit -m 'one\nthread grep two'",
                 "echo 'see (thread grep x)'", "copy thread grep notes.txt", "cat <<'EOF'\nthread grep x\nEOF"]
        for c in hit:
            self.assertTrue(thread.runs_grep(c), c)
        for c in miss:
            self.assertFalse(thread.runs_grep(c), c)
        self.run_cli("new", "A")
        use = lambda i, c: msg("assistant", [{"type": "tool_use", "id": i, "name": "Bash", "input": {"command": c}}])
        res = lambda i, t: msg("user", [{"type": "tool_result", "tool_use_id": i, "content": t}])
        self.say(use("g1", "thread grep x"), use("c1", miss[0]))
        self.hook()  # the results arrive in a later capture than the calls
        self.say(res("c1", "commit output kept"), res("g1", "grep output dropped"),
                 res("g1", "same id again is kept"))
        self.hook()
        self.assertIn("grep output dropped", self.log("a"))  # stored: the log keeps everything
        count = lambda rx: self.run_cli("grep", rx, "--count").strip()
        self.assertEqual(count("commit output kept"), "1")
        self.assertEqual(count("grep output dropped|same id again"), "0")  # but not searched
        self.assertEqual(count("thread grep"), "1")  # the commit message; not the grep call itself

    def test_grep_output_shape_defaults_and_page_one_capture(self):
        self.run_cli("new", "A")
        for i in range(41):
            self.run_cli("note", f"line {i}")
        page = self.run_cli("grep", "line 7$").splitlines()
        self.assertRegex(page[0], r"^a:\d+  === \S+ sess-1 note ===$")
        self.assertEqual(page[1], f"> {self.log('a').splitlines().index('line 7') + 1}: line 7")
        self.assertEqual(len(page), 3)  # location, the match, footer: context stays inside the entry
        self.assertEqual(self.run_cli("grep", "^line", "--max", "99", "--context", "0").count("\n> "), 30)
        self.assertIn("[matches 1-30 of 41; next page: --offset 30]",
                      self.run_cli("grep", "^line", "--max", "99", "--context", "0"))
        self.assertIn("[matches 31-40 of 41; next page: --offset 40]",
                      self.run_cli("grep", "^line", "--offset", "30"))
        with self.assertRaises(SystemExit):
            self.run_cli("grep", "x", "--all", "-t", "a")
        self.say(msg("user", "fresh words"))
        self.assertIn("[matches 0-0 of 0]", self.run_cli("grep", "fresh words", "--offset", "1"))
        self.assertIn("[matches 1-1 of 1]", self.run_cli("grep", "fresh words"))  # page 1 captures
        # an earlier grep call holds its own pattern and is left out of later searches
        for n in range(3):
            self.say(msg("assistant", [{"type": "tool_use", "id": f"g{n}", "name": "Bash",
                                        "input": {"command": 'thread grep "fresh words" --max 1'}}]))
        self.assertIn("[matches 1-1 of 1]", self.run_cli("grep", "fresh words", "--max", "1"))

    def test_open_shows_only_what_follows_the_last_checkpoint(self):
        self.run_cli("new", "A")
        self.run_cli("note", "old note")
        self.run_cli("checkpoint", "  Goal: g  ")
        self.assertEqual(thread.summary("a"), "Goal: g\n")
        self.assertIn("checkpoint", self.kinds("a"))
        self.assertNotIn("entries since", self.run_cli("open", "a"))
        self.say(*[msg("user", f"message {i} " + "w" * 700) for i in range(8)])
        self.run_cli("note", "new note")
        out = self.run_cli("open", "a")
        self.assertIn("9 entries since the last checkpoint", out)
        self.assertNotIn("old note", out)
        self.assertIn("new note", out)
        self.assertNotIn("message 1 ", out)  # only the last 6 messages
        self.assertIn("message 2 ", out)
        self.assertNotIn("w" * 601, out)  # each clipped to 600 characters
        self.assertLess(self.log("a").index("message 7"), self.log("a").index("new note"))  # captured first

    def test_binding_does_not_outlive_close_or_removal_by_another_session(self):
        self.run_cli("new", "A")
        self.as_session("sess-2")
        self.run_cli("close", "-t", "a", "Outcome: done")
        self.run_cli("reopen", "a")
        with self.assertRaises(SystemExit):
            self.run_cli("reopen", "a")  # already open
        self.assertEqual(self.kinds("a")[-2:], ["event", "event"])
        self.assertIn("closed\n", self.log("a"))
        self.assertIn("reopened\n", self.log("a"))
        self.as_session(SID)
        self.say(msg("user", "after close and reopen elsewhere"))
        self.assertNotIn("Active thread", self.hook("SessionStart"))  # no longer this session's thread
        self.assertNotIn("after close and reopen elsewhere", self.log("a"))
        self.run_cli("new", "B")
        import shutil
        shutil.rmtree(thread.home() / "b")
        self.as_session("sess-2")
        self.run_cli("new", "B")
        self.as_session(SID)
        self.say(msg("user", "meant for the removed thread"))
        self.hook()
        self.assertNotIn("meant for the removed thread", self.log("b"))

    def test_ids_list_order_and_file_modes(self):
        self.run_cli("new", "x" * 80)
        self.assertEqual(thread.active(SID), "x" * 50)
        self.run_cli("new", "First")
        self.run_cli("new", "Second one")
        with self.assertRaises(SystemExit):
            self.run_cli("open", "one")  # a prefix, not a substring
        rows = self.run_cli("list").splitlines()
        self.assertTrue(rows[0].startswith("* second-one"))
        self.assertTrue(rows[1].startswith("  first"))
        self.run_cli("checkpoint", "s")
        if os.name == "posix":
            for f in ("second-one/meta.json", "second-one/summary.md", f".sessions/{SID}.json"):
                self.assertEqual((thread.home() / f).stat().st_mode & 0o777, 0o600, f)
            os.chmod(thread.home(), 0o755)  # an existing folder keeps the mode its owner gave it
            self.run_cli("note", "x")
            self.assertEqual(thread.home().stat().st_mode & 0o777, 0o755)
            os.chmod(self.transcript, 0)  # capture fails; the note must still be written
            self.run_cli("note", "kept despite capture failure")
            os.chmod(self.transcript, 0o600)
            self.assertIn("kept despite capture failure", self.log("second-one"))

    def test_hook_reads_given_transcript_and_survives_damaged_state(self):
        self.run_cli("new", "A")
        elsewhere = Path(self.tmp.name) / "elsewhere.jsonl"
        elsewhere.write_text(msg("user", "from the given path"))
        self.run_cli("hook", stdin=json.dumps({"session_id": SID, "transcript_path": str(elsewhere)}))
        self.assertIn("from the given path", self.log("a"))
        st = thread.state(SID)
        st["offset"] = 99  # beyond the transcript: start again from the top
        thread.state_path(SID).write_text(json.dumps(st))
        self.say(msg("user", "after offset reset"))
        self.hook()
        self.assertIn("after offset reset", self.log("a"))
        for bad in ("[1]", '"x"', '{"thread": 5}'):
            thread.state_path(SID).write_text(bad)
            self.assertNotIn("Active thread", self.hook("SessionStart"))
            self.run_cli("list")
        (thread.home() / "a" / "meta.json").write_text("{}")
        self.run_cli("list", "--all")
        self.assertFalse((thread.home() / "errors.log").exists())
        self.run_cli("hook", stdin="x")
        self.run_cli("hook", stdin="y")
        self.assertEqual((thread.home() / "errors.log").read_text().count("Traceback"), 2)  # appended


    def test_feedback_and_what_is_printed_back(self):
        self.say(msg("user", "before the thread"))
        self.assertEqual(self.run_cli("new", "A"), "created thread a; 1 earlier transcript lines of this session "
                         "were captured into it\n")
        self.assertIn("now captured into it, no longer into a", self.run_cli("new", "B"))
        self.assertIn("write a fresh `thread checkpoint` now", self.hook("SessionStart"))  # none yet
        self.run_cli("checkpoint", "Goal: g")
        self.assertNotIn("out of date", self.hook("SessionStart"))
        self.assertEqual(self.run_cli("note", stdin="\ufeffwith a BOM \x1b]0;TITLE\x07 and escapes\n"),
                         "noted in b (1 entries since the last checkpoint)\n")
        self.assertIn("\nwith a BOM", self.log("b"))
        self.assertIn("1 entries were logged after this summary", self.hook("SessionStart"))
        for out in (self.run_cli("grep", "BOM"), self.run_cli("open", "b")):
            self.assertIn("with a BOM ]0;TITLE and escapes", out)  # control characters removed
            self.assertNotIn("\x1b", out)
        self.say(msg("user", "Claude Code's own compaction summary", isCompactSummary=True))
        self.hook()
        self.assertIn(" compaction ===\nClaude Code's own compaction summary\n", self.log("b"))
        self.assertNotIn("errors.log", self.run_cli("list"))
        self.run_cli("hook", stdin="x")
        self.assertIn("hook errors are recorded in", self.run_cli("list"))
        old, sys.stdin = sys.stdin, None
        try:
            with self.assertRaises(SystemExit):
                thread.read_text([])
        finally:
            sys.stdin = old

    def test_grep_groups_an_entry_and_only_real_grep_calls_are_left_out(self):
        self.run_cli("new", "A")
        self.run_cli("note", stdin="alpha hit\nx1\nbeta hit\nx2\nx3\nx4\nx5\ngamma hit\n")
        page = self.run_cli("grep", "hit").splitlines()
        self.assertRegex(page[0], r"^a:3  === \S+ sess-1 note ===$")  # one header for the entry
        self.assertEqual([re.sub(r"\d+: ", "", l) for l in page[1:-1]],
                         ["> alpha hit", "  x1", "> beta hit", "  x2", "  --", "  x5", "> gamma hit"])
        self.assertEqual(page[-1], "[matches 1-3 of 3]")
        use = lambda i, tool, inp: msg("assistant", [{"type": "tool_use", "id": i, "name": tool, "input": inp}])
        res = lambda i, t: msg("user", [{"type": "tool_result", "tool_use_id": i, "content": t}])
        self.say(use("w1", "Write", {"file_path": "a.py", "content": 'run("thread grep foo")'}), res("w1", "wrote Zed1"),
                 use("h1", "Bash", {"command": "cat > notes <<'EOF'\nthread grep 'x'\nEOF\necho Zed2"}), res("h1", "Zed2"),
                 use("g1", "Bash", {"command": "cd /r && thread grep Zed"}), res("g1", "a:9 Zed3"))
        self.hook()
        self.assertEqual(self.run_cli("grep", "Zed", "--count").splitlines()[0], "3")  # Zed1 and Zed2 (twice)
        self.run_cli("note", stdin="first line\nsecond mark\nthird\nfourth mark\n")
        page = self.run_cli("grep", "mark").splitlines()
        self.assertEqual([re.sub(r"\d+: ", "", l) for l in page[1:-1]],  # context reaches the entry's first line
                         ["  first line", "> second mark", "  third", "> fourth mark"])
        page = self.run_cli("grep", "mark", "--context", "0").splitlines()
        self.assertEqual([re.sub(r"\d+: ", "", l) for l in page[1:-1]], ["> second mark", "  --", "> fourth mark"])
        # newest first is by entry time, not by thread name
        self.run_cli("new", "Zzz")
        self.say(msg("user", "an old mark, in a thread that sorts last"))
        self.hook()
        page = self.run_cli("grep", "mark", "--all", "--type", "user,note")
        self.assertLess(page.index("fourth mark"), page.index("an old mark"))

    def test_reminder_folder_match_ids_types_and_fork_boundary(self):
        base = Path(self.tmp.name).resolve()
        for d in ("app", "app2", "app/sub"):
            (base / d).mkdir(parents=True)
        old = os.getcwd()
        try:
            os.chdir(base / "app")
            self.run_cli("new", "In app")
            os.chdir("/")
            self.run_cli("new", "In root")
        finally:
            os.chdir(old)
        self.as_session("sess-2")
        start = lambda cwd: self.hook("SessionStart", source="startup", cwd=str(cwd))
        self.assertIn("this folder: in-app. None", start(base / "app"))
        self.assertIn("this folder: in-app. None", start(base / "app" / "sub"))
        self.assertEqual(start(base / "app2"), "")  # a path test, not a string prefix
        self.assertEqual(start(base), "")
        # calls without an id: one grep call must not hide the others
        self.as_session(SID)
        use = lambda c: msg("assistant", [{"type": "tool_use", "name": "Ba\x1b[31msh", "input": {"description": "d", "command": c}}])
        res = lambda t: msg("user", [{"type": "tool_result", "content": t}])
        self.say(use("thread grep x"), res("Qgrep"), use("ls"), res("Qls"))
        self.hook()
        out = self.run_cli("grep", "Q(grep|ls)|command: ls")
        self.assertIn("Qls", out)
        self.assertNotIn("\x1b", out)  # a control character in a tool name does not reach the terminal
        with self.assertRaises(SystemExit):
            self.run_cli("grep", "x", "--type", "decision")
        # with ids, `command` need not be the first key
        self.say(msg("assistant", [{"type": "tool_use", "id": "k1", "name": "Bash",
                                    "input": {"description": "d", "command": "thread grep Zq"}}]),
                 msg("user", [{"type": "tool_result", "tool_use_id": "k1", "content": "Zq found"}]))
        self.hook()
        self.assertEqual(self.run_cli("grep", "Zq", "--count").strip(), "0")
        # a fork: the parent's lines of the very second the fork began are still the parent's
        fork = self.transcript.with_name("sess-3.jsonl")
        fork.write_text("")
        self.as_session("sess-3")
        self.hook("SessionStart", source="fork")
        since = thread.state("sess-3")["since"]
        fork.write_text(msg("user", "parent, same second").replace(SID, "sess-3").replace("2026-01-01T00:00:00", since[:19]))
        self.run_cli("new", "F")
        self.assertNotIn("parent, same second", self.log("f"))

    def test_open_without_a_transcript_in_reach_escapes_and_corrupt_meta(self):
        self.run_cli("new", "Plain \x1b[31mtitle")
        self.assertEqual(thread.meta("plain-31mtitle")["title"], "Plain [31mtitle")
        self.run_cli("note", "esc \x1b]0;x\x07 note")
        self.assertNotIn("\x1b", self.run_cli("export", "plain") + self.run_cli("list") + self.run_cli("open", "plain"))
        # a session whose transcript the CLI cannot find: `open` must still not capture what came before
        self.as_session("sess-9")
        hidden = Path(self.tmp.name) / "elsewhere" / "t.jsonl"
        hidden.parent.mkdir()
        hidden.write_text(msg("user", "said before the open").replace(SID, "sess-9"))
        self.run_cli("open", "plain")
        this_second = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        with open(hidden, "a") as f:
            f.write(msg("user", "said right after the open").replace(SID, "sess-9").replace("2026-01-01T00:00:00", this_second))
            f.write(msg("user", "said after the open").replace(SID, "sess-9").replace("2026-01-01", "2099-01-01"))
        self.run_cli("hook", stdin=json.dumps({"session_id": "sess-9", "transcript_path": str(hidden)}))
        log = self.log("plain-31mtitle")
        self.assertNotIn("said before the open", log)
        self.assertIn("said after the open", log)
        self.assertIn("said right after the open", log)  # the same second as the open is kept
        self.run_cli("hook", stdin="")  # run by hand with nothing on stdin: no error recorded
        self.assertFalse((thread.home() / "errors.log").exists())
        (thread.home() / "plain-31mtitle" / "meta.json").write_text("{")
        with self.assertRaises(SystemExit) as e:
            self.run_cli("open", "plain")
        self.assertEqual(e.exception.code, 1)  # a message, not a traceback

    def test_parallel_commands_do_not_duplicate_and_a_stale_lock_is_taken_over(self):
        self.run_cli("new", "A")
        self.say(*[msg("user", f"line {i:03d} of the turn") for i in range(200)])
        script = str(Path(thread.__file__).resolve())
        procs = [subprocess.Popen([sys.executable, script, "note", f"parallel {i}"], env=dict(os.environ),
                                  stdout=subprocess.DEVNULL) for i in range(8)]
        self.assertEqual([p.wait() for p in procs], [0] * 8)
        log = self.log("a")
        self.assertEqual([log.count(f"line {i:03d} of the turn") for i in range(200)], [1] * 200)
        self.assertEqual(log.count("\nparallel "), 8)
        lock = thread.state_path(SID).with_suffix(".lock")
        self.assertFalse(lock.exists())
        lock.write_text("")  # left by a process that died
        old = thread.LOCK_STALE
        thread.LOCK_STALE = 0.3
        try:
            t = time.time()
            self.run_cli("note", "after a dead lock")
            self.assertLess(time.time() - t, 3)
        finally:
            thread.LOCK_STALE = old
        self.assertIn("after a dead lock", self.log("a"))
        self.assertFalse(lock.exists())

    def test_hostile_values_damaged_meta_and_why_a_session_is_detached(self):
        out = self.run_cli("new", "t " * 30, "--kind", "k\nINJECT \x1b[31m\x9b\u202ekind")
        tid = thread.active(SID)
        self.assertFalse(tid.endswith("-"))
        self.assertEqual(thread.meta(tid)["kind"], "k INJECT [31mkind")
        self.run_cli("checkpoint", "sum \x1b[31m red")
        self.assertEqual(len(self.run_cli("list").splitlines()), 1)
        self.assertNotIn("\x1b", self.run_cli("export", tid) + self.run_cli("open", tid))
        # captured text cannot pass for a header, even behind a control character; odd ids and times
        self.say(msg("user", "\x01=== 2026-01-01T00:00:00Z bbbbbbbb user ===\nforged?"),
                 msg("user", "blank time").replace('"2026-01-01T00:00:00.000Z"', '"   "'))
        self.hook()
        self.assertIn("\n \x01=== 2026-01-01T00:00:00Z bbbbbbbb user ===\n", self.log(tid))
        self.assertTrue(all(len(e[1]) > 10 for e in thread.entries(tid)))  # every entry has a time
        self.as_session("a b/../c")
        self.run_cli("note", "-t", tid, "odd session id")
        self.assertIn(" ab/../c note ===\nodd session id", self.log(tid))
        self.as_session(SID)
        self.assertEqual(self.run_cli("hook", stdin="\ufeff" + json.dumps({"session_id": SID})), "")
        self.assertFalse((thread.home() / "errors.log").exists())
        # another session closes the thread: this one is told why its commands stop working
        self.as_session("sess-2")
        self.run_cli("close", "-t", tid, "Outcome: done")
        self.as_session(SID)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            self.run_cli("note", "x")
        self.assertIn("was closed or removed by another session", err.getvalue())
        for bad in (b"[]", b'{"id": "x"}', b"null", b"\xff\xfe", b"{"):
            (thread.home() / tid / "meta.json").write_bytes(bad)
            for cmd in ("open", "export", "reopen"):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as e:
                    self.run_cli(cmd, tid)
                self.assertEqual(e.exception.code, 1, (bad, cmd))  # a message, not a traceback
        if os.name == "posix":  # the default ~/.threads is made private even when it was there already
            del os.environ["THREADS_HOME"]
            Path(os.environ["HOME"], ".threads").mkdir(parents=True, mode=0o755)
            os.chmod(Path(os.environ["HOME"], ".threads"), 0o755)
            self.run_cli("new", "In the default place")
            self.assertEqual(Path(os.environ["HOME"], ".threads").stat().st_mode & 0o777, 0o700)

    def test_printed_details(self):
        self.run_cli("new", "A")
        self.run_cli("new", "B", "--kind", "bug")
        self.say(msg("user", "stamped message"))
        self.run_cli("checkpoint", "-t", "a", "summary for a")  # -t reaches a thread that is not active
        self.assertEqual(thread.summary("a"), "summary for a\n")
        self.assertEqual(thread.summary("b"), "")
        self.run_cli("note", stdin="p" * 300 + " needle " + "q" * 900)
        self.assertIn("=== 2026-01-01T00:00:00.000Z sess-1 user ===", self.log("b"))  # transcript time kept
        stamp = next(e[1] for e in thread.entries("b") if e[3] == "note")
        self.assertIn(f"- {stamp}: ppp", self.run_cli("export", "b"))
        self.assertIn(f"[{stamp} note] ppp", self.run_cli("open", "b"))
        self.assertIn("kind=-", self.run_cli("open", "a"))
        self.assertIn("* a  -  open", self.run_cli("list"))  # `open a` made it active
        page = self.run_cli("grep", "needle", "--context", "0", "-t", "b").splitlines()
        self.assertEqual(len(page), 3)  # location, the match alone, footer
        self.assertEqual(page[1], "> 6: …" + "p" * 149 + " needle " + "q" * 243 + "…")
        self.assertEqual(self.run_cli("grep", "^created", "--context", "3", "-t", "a").count("created: A"), 1)
        self.assertNotIn("cut at", self.hook("SessionStart"))
        self.run_cli("checkpoint", stdin="S" * (thread.CAP + 1))
        self.assertIn(f"cut at {thread.CAP} characters", self.hook("SessionStart"))


if __name__ == "__main__":
    unittest.main()
