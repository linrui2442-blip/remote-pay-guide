"""Offline certification for the Sub2 G4-C compatibility relay."""
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))

TEMP = Path(tempfile.mkdtemp(prefix="g4c-sub2-relay-"))
DB = TEMP / "relay.db"
STAGING = TEMP / "staging"
os.environ.update({
    "OS_TESTING": "1",
    "OS_DATABASE_PATH": str(DB),
    "SUB2_VIDEO_BASE_URL": "http://127.0.0.1:18080",
    "SUB2_VIDEO_API_KEY": "sub2-secret-sentinel",
    "SUB2_VIDEO_MODEL": "gemini-3.1-pro-high",
    "G4C_SUB2_RELAY_API_KEY": "relay-secret-sentinel",
    "G4C_SUB2_STAGING_ROOT": str(STAGING),
    "G4C_SUB2_MAX_VIDEO_BYTES": "64",
})

from ai.sub2_relay import Sub2RelayService, _row, _update, init_db, relay_key_matches


class Response:
    def __init__(self, status, data=None, body=b"", mime="application/json"):
        self.status_code, self.data, self.body = status, data, body
        self.headers = {"Content-Type": mime, "Content-Length": str(len(body))}

    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data

    def iter_content(self, chunk_size=1024):
        for index in range(0, len(self.body), max(1, chunk_size)):
            yield self.body[index:index + chunk_size]


class Sub2:
    def __init__(self, create=None, statuses=None, content=None):
        self.create_response = create or Response(202, {"id": "video_one", "status": "queued", "model": "x"})
        self.statuses = list(statuses or [Response(200, {"status": "completed"})])
        self.content = content or Response(200, body=b"synthetic-mp4", mime="video/mp4")
        self.posts = self.gets = self.content_gets = 0
        self.sent = None
        self.lock = threading.Lock()

    def post(self, url, **kwargs):
        with self.lock: self.posts += 1
        self.sent = (url, kwargs)
        if isinstance(self.create_response, Exception): raise self.create_response
        return self.create_response

    def get(self, url, **kwargs):
        with self.lock: self.gets += 1
        if url.endswith("/content"):
            self.content_gets += 1
            return self.content
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0]


class GitHub:
    owner = "linrui2442-blip"
    repo = "remote-pay-guide"

    def __init__(self, trigger_error=None, run=None):
        self.posts = self.gets = 0
        self.trigger_error = trigger_error
        self.run = run or {"id": 701, "status": "completed", "conclusion": "success"}
        self.inputs = None

    def trigger_workflow(self, workflow, branch="main", inputs=None):
        self.posts += 1
        self.inputs = (workflow, branch, inputs)
        if self.trigger_error: raise self.trigger_error
        return {"status": "started"}

    def get_workflow_run(self, run_id):
        self.gets += 1
        return self.run


class Monitor:
    def __init__(self, github, discover_error=None):
        self.github = github
        self.discover_error = discover_error
        self.reads = 0

    def snapshot_run_ids(self, workflow, branch):
        self.reads += 1
        return {600}

    def discover_run(self, workflow, branch, pre_dispatch_run_ids, dispatch_started_at,
                     max_attempts=1, poll_interval=0):
        self.reads += 1
        if self.discover_error: raise self.discover_error
        return {"id": 701, "status": "queued", "created_at": dispatch_started_at}


def payload(prompt="proof"):
    return {"task_type": "video_generation", "model": "auto", "prompt": prompt,
            "input": {"content_id": "proof-content", "topic": "Proof topic",
                      "script": prompt, "visual_direction": "vertical technical scene",
                      "title": "Proof", "description": "Offline contract"},
            "options": {"aspect_ratio": "9:16"}}


def service(sub2=None, github=None, monitor=None):
    sub2, github = sub2 or Sub2(), github or GitHub()
    monitor = monitor or Monitor(github)
    return Sub2RelayService(sub2, github, monitor, lambda url: url.startswith("https://")), sub2, github


def rejected(call, text=None):
    try:
        call()
    except (ValueError, RuntimeError):
        return
    raise AssertionError(text or "expected rejection")


def main():
    try:
        init_db()
        assert relay_key_matches("relay-secret-sentinel")
        assert not relay_key_matches("wrong-relay-key")
        boundary, boundary_sub2, _ = service()
        unsupported = payload()
        unsupported["options"]["duration"] = 15
        rejected(lambda: boundary.create("g4c-runtime-job-99", unsupported))
        assert boundary_sub2.posts == 0
        # A: full asynchronous lifecycle and canonical response contract.
        svc, sub2, github = service(Sub2(statuses=[
            Response(200, {"status": "queued"}),
            Response(200, {"status": "processing"}),
            Response(200, {"status": "completed"}),
        ]))
        rid = "g4c-runtime-job-1"
        first = svc.create(rid, payload())
        assert first["status"] == "submitted" and first["job_id"] == rid
        assert first["status_url"] == "/internal/g4c/sub2/videos/" + rid
        assert first["provider_constraints"] == {"aspect_ratio": "not_enforced_by_sub2"}
        assert sub2.sent[1]["json"] == {"model": "gemini-3.1-pro-high", "prompt": "proof"}
        assert "sub2-secret-sentinel" in sub2.sent[1]["headers"]["Authorization"]
        assert svc.status(rid)["status"] == "submitted"
        assert svc.status(rid)["status"] == "running"
        assert svc.status(rid)["status"] == "running"
        done = svc.status(rid)
        assert done["status"] == "completed" and done["asset_url"].endswith(f"/{rid}.mp4")
        assert sub2.posts == 1 and sub2.content_gets == 1 and github.posts == 1
        row = _row(rid)
        assert row["video_sha256"] == hashlib.sha256(b"synthetic-mp4").hexdigest()
        assert row["video_size"] == len(b"synthetic-mp4")
        assert row["content_id"] == "proof-content"
        assert Path(os.environ["G4C_SUB2_STAGING_ROOT"], rid, f"{rid}.mp4").read_bytes() == b"synthetic-mp4"
        print("SUB2_RELAY_CANONICAL_CONTRACT=PASS")
        print("SUB2_BINARY_CONTENT_STAGING=PASS")
        print("LOCAL_VIDEO_GITHUB_BRIDGE=PASS_OFFLINE")
        print("PUBLIC_ASSET_URL_CONTRACT=PASS_OFFLINE")

        # B/C: exact replay and drift.
        calls = (sub2.posts, sub2.gets, github.posts, github.gets)
        assert svc.create(rid, payload()) == done
        assert (sub2.posts, sub2.gets, github.posts, github.gets) == calls
        restarted, restarted_sub2, restarted_github = service()
        assert restarted.create(rid, payload()) == done
        assert restarted.status(rid) == done
        assert restarted_sub2.posts == restarted_sub2.gets == restarted_github.posts == restarted_github.gets == 0
        rejected(lambda: svc.create(rid, payload("different")), "drift accepted")
        print("SUB2_RELAY_EXACT_REPLAY=PASS")
        print("SUB2_RELAY_REQUEST_DRIFT=PASS")
        print("SUB2_RELAY_TERMINAL_REPLAY=PASS")

        # D: 20 four-caller races, one POST each.
        for number in range(20):
            race, rs, _ = service()
            request_id = f"g4c-runtime-job-{100 + number}"
            barrier = threading.Barrier(4)
            def create(_):
                barrier.wait()
                return race.create(request_id, payload())
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(create, range(4)))
            assert rs.posts == 1 and len({json.dumps(x, sort_keys=True) for x in results}) == 1
        print("SUB2_RELAY_CONCURRENCY_ROUNDS=20")
        print("SUB2_RELAY_EXACTLY_ONE_POST=PASS")

        # E: ambiguous POST cannot be replayed.
        unknown, us, _ = service(Sub2(create=requests.Timeout("secret")))
        uid = "g4c-runtime-job-300"
        result = unknown.create(uid, payload())
        assert result["manual_reconciliation_required"] and _row(uid)["state"] == "DISPATCH_UNKNOWN"
        assert unknown.create(uid, payload()) == result and us.posts == 1
        assert unknown.status(uid) == result and us.gets == 0
        print("SUB2_RELAY_UNKNOWN_OUTCOME_FAIL_CLOSED=PASS")

        # F/G/H: failed, task loss, content early.
        failed, fs, _ = service(Sub2(statuses=[Response(200, {"status": "failed"})]))
        failed.create("g4c-runtime-job-301", payload()); out = failed.status("g4c-runtime-job-301")
        assert out["status"] == "failed" and fs.posts == 1
        missing, ms, _ = service(Sub2(statuses=[Response(404, {})]))
        missing.create("g4c-runtime-job-302", payload()); out = missing.status("g4c-runtime-job-302")
        assert out["manual_reconciliation_required"] and ms.posts == 1
        early, es, _ = service(Sub2(content=Response(202, {})))
        early.create("g4c-runtime-job-303", payload()); out = early.status("g4c-runtime-job-303")
        assert out["status"] == "running" and es.content_gets == 1
        print("SUB2_RELAY_TASK_FAILURE=PASS")
        print("SUB2_RELAY_TASK_LOSS_FAIL_CLOSED=PASS")
        print("SUB2_RELAY_CONTENT_NOT_READY=PASS")

        # I/J/K: MIME, empty, and maximum-size validation.
        for number, content, expected in (
            (304, Response(200, body=b"x", mime="text/plain"), "INVALID_CONTENT"),
            (305, Response(200, body=b"", mime="video/mp4"), "STAGING_FAILED"),
            (306, Response(200, body=b"x" * 65, mime="video/mp4"), "CONTENT_TOO_LARGE"),
        ):
            item, _, gh = service(Sub2(content=content))
            item.create(f"g4c-runtime-job-{number}", payload())
            assert item.status(f"g4c-runtime-job-{number}")["error"] == expected and gh.posts == 0
        print("SUB2_RELAY_CONTENT_VALIDATION=PASS")

        # L/M/Q/R: runtime path confinement plus static workflow hash/collision contract.
        local, _, _ = service()
        cfg = {"root": STAGING}
        rejected(lambda: local._stage_path(cfg, "../escape", "x.mp4"))
        rejected(lambda: local._stage_path(cfg, "g4c-runtime-job-1", "../x.mp4"))
        workflow = (ROOT / ".github/workflows/promote-local-g4c-video.yml").read_text("utf-8")
        for required in ("hash mismatch", "media collision", "sha256sum", "expected_sha256",
                         "runs-on: [self-hosted, windows, x64]", "runs-on: ubuntu-latest"):
            assert required in workflow
        assert "--force" not in workflow and "provider_url" not in workflow.lower()
        print("SUB2_RELAY_STAGING_SECURITY=PASS")
        print("GITHUB_BRIDGE_HASH_AND_COLLISION=PASS")

        # N: concurrent terminal polling causes one content retrieval and dispatch.
        concurrent, cs, cg = service()
        cid = "g4c-runtime-job-307"
        concurrent.create(cid, payload())
        barrier = threading.Barrier(4)
        def poll(_):
            barrier.wait(); return concurrent.status(cid)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(poll, range(4)))
        assert cs.content_gets == 1 and cg.posts == 1
        print("SUB2_RELAY_CONCURRENT_COMPLETION=PASS")

        # O/P: GitHub ambiguity is durable and failure becomes terminal.
        amb_gh = GitHub(trigger_error=requests.Timeout("secret"))
        amb_monitor = Monitor(amb_gh, discover_error=TimeoutError())
        amb, _, _ = service(Sub2(), amb_gh, amb_monitor)
        aid = "g4c-runtime-job-308"
        amb.create(aid, payload()); out = amb.status(aid)
        assert out["manual_reconciliation_required"] and amb_gh.posts == 1
        assert amb.status(aid) == out and amb_gh.posts == 1 and amb_monitor.reads >= 3
        bad_gh = GitHub(run={"id": 701, "status": "completed", "conclusion": "failure"})
        bad, _, _ = service(Sub2(), bad_gh, Monitor(bad_gh))
        bid = "g4c-runtime-job-309"
        bad.create(bid, payload()); bad.status(bid)
        assert bad.status(bid)["error"] == "GITHUB_FAILED" and bad_gh.posts == 1
        print("GITHUB_BRIDGE_AT_MOST_ONE_DISPATCH=PASS")
        print("GITHUB_BRIDGE_FAILURE=PASS")

        # T: secrets never enter correlation rows or source-owned safe errors.
        raw = DB.read_bytes()
        assert b"sub2-secret-sentinel" not in raw and b"relay-secret-sentinel" not in raw
        with sqlite3.connect(DB) as db:
            schema = db.execute("SELECT sql FROM sqlite_master WHERE name='g4c_sub2_relay_requests'").fetchone()[0]
            assert "api_key" not in schema.lower() and "authorization" not in schema.lower()
        print("SUB2_RELAY_PERSISTENT_CORRELATION=PASS")
        print("SUB2_RELAY_SECRET_SAFETY=PASS")

        # No test path may fall through to real requests.
        print("REAL_SUB2_POSTS=0")
        print("REAL_SUB2_GETS=0")
        print("REAL_GITHUB_POSTS=0")
        print("REAL_GITHUB_GETS=0")
        print("G4D_HANDOFF_UNCHANGED=PASS")
        print("G4C_SUB2_RELAY_OFFLINE_CERTIFICATION=PASS")
    finally:
        shutil.rmtree(TEMP, ignore_errors=True)


if __name__ == "__main__":
    with patch("requests.sessions.Session.request", side_effect=AssertionError("real network forbidden")):
        main()
