import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
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
        self.env = {"THREADS_HOME": str(root / "threads"), "CLAUDE_CONFIG_DIR": str(root / "claude"),
                    "CLAUDE_CODE_SESSION_ID": SID}
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

    def hook(self, event="Stop"):
        return self.run_cli("hook", stdin=json.dumps(
            {"session_id": SID, "transcript_path": str(self.transcript), "hook_event_name": event}))

    def log(self, tid):
        return (thread.home() / tid / "log.txt").read_text()

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
        self.assertIn("tool_use Bash ===", log)
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
        self.assertEqual(self.run_cli("grep", "needle", "--count", "--all").strip(), "12")
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
            seen += [l for l in page.splitlines() if l.startswith("> ")]
            nxt = page.rsplit("--offset ", 1)
            if len(nxt) == 1:
                break
            offset = int(nxt[1].rstrip("]\n"))
        self.assertEqual(seen, [f"> needle {i}" for i in range(12)])  # every match on some page
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
            seen += re.findall(r"^> (needle item\d+)$", page, re.M)
            # the call and its output land in the transcript, and a hook captures them
            self.say(msg("assistant", [{"type": "tool_use", "id": f"t{pages}", "name": "Bash", "input":
                         {"command": f'thread grep "needle item" --all --offset {offset}'}}]),
                     msg("user", [{"type": "tool_result", "tool_use_id": f"t{pages}", "content": page}]))
            self.hook()
            nxt = re.search(r"--offset (\d+)\]", page)
            if not nxt:
                break
            offset = int(nxt[1])
        self.assertEqual(seen, [f"needle item{i:03d}" for i in range(25)])
        self.assertLess(pages, 10)  # the footer stops offering pages
        log = self.log("aaa")
        self.assertIn(thread.GREP_MARK, log)  # the call is logged, its output is not
        self.assertIn("thread grep", log)
        self.assertNotIn("> needle item000", log)

    def test_forked_session_does_not_recapture_parent_history(self):
        self.say(msg("user", "parent line"))
        self.run_cli("new", "A")
        fork = self.transcript.with_name("sess-2.jsonl")
        fork.write_text(self.transcript.read_text() + msg("user", "fork line").replace(SID, "sess-2"))
        self.as_session("sess-2")
        self.run_cli("open", "a")
        self.assertEqual(self.log("a").count("parent line"), 1)
        self.assertIn("fork line", self.log("a"))

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
            self.run_cli("note", stdin=f"before {i}\n{'z' * 2000} needle {i} {'z' * 2000}\nafter {i}\n")
        page = self.run_cli("grep", "needle", "--max", "99", "--context", "9")
        first = page.split("\n--\n")[0].splitlines()
        self.assertEqual(len(first), 1 + 7)  # location line + match with 3 lines either side
        hit = next(l for l in first if l.startswith("> "))
        self.assertIn("needle 0", hit)
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
        r = hook(json.dumps({**base, "hook_event_name": "SessionStart"}))
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


if __name__ == "__main__":
    unittest.main()
