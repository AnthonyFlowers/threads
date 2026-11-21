import contextlib
import io
import json
import os
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


if __name__ == "__main__":
    unittest.main()
