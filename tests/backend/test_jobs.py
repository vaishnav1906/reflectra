"""The background job runner: finishes, retries, gives up, and keeps one job per person at a time."""

import asyncio
import unittest
import uuid

from app.services import job_service as js
from app.services.llm import LLMRateLimited


class FakeSession:
    def __init__(self, log):
        self.log = log

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, statement, params=None):
        self.log.append((str(statement).split()[0:6], dict(params or {})))

    async def commit(self):
        pass

    async def rollback(self):
        self.log.append(("rollback", {}))


def outcome(log):
    """The UPDATE that closed the job: done, retried (queued) or failed."""
    for words, params in reversed(log):
        if isinstance(words, list) and words[:1] == ["UPDATE"]:
            text = " ".join(words)
            if "'done'" in text:
                return "done"
            if "'queued'" in text:
                return "retry"
            if "'failed'" in text:
                return "failed"
    return None


class Runner(unittest.TestCase):
    def setUp(self):
        self.log = []
        self.factory = lambda: FakeSession(self.log)
        self.user = uuid.uuid4()

    def job(self, kind, attempts=1):
        return {"id": uuid.uuid4(), "user_id": self.user, "kind": kind, "payload": {}, "attempts": attempts}

    def run_job(self, job):
        asyncio.run(js.run_one(job, self.factory))
        return outcome(self.log)

    def test_success_marks_done(self):
        @js.handler("t_ok")
        async def ok(db, user_id, payload):
            return None

        self.assertEqual(self.run_job(self.job("t_ok")), "done")

    def test_busy_ai_is_retried_later(self):
        @js.handler("t_busy")
        async def busy(db, user_id, payload):
            raise LLMRateLimited("all busy")

        self.assertEqual(self.run_job(self.job("t_busy", attempts=1)), "retry")
        self.assertEqual(self.log[-1][1]["wait"], 20)

    def test_gives_up_after_the_last_attempt(self):
        @js.handler("t_broken")
        async def broken(db, user_id, payload):
            raise RuntimeError("bug")

        self.assertEqual(self.run_job(self.job("t_broken", attempts=js.MAX_ATTEMPTS)), "failed")

    def test_unknown_jobs_fail_without_retrying(self):
        self.assertEqual(self.run_job(self.job("nobody_handles_this")), "failed")

    def test_backoff_grows(self):
        self.assertEqual([js.backoff(n) for n in (1, 2, 3, 4)], [20, 60, 180, 180])

    def test_one_job_at_a_time_per_person(self):
        order = []

        @js.handler("t_slow")
        async def slow(db, user_id, payload):
            order.append("start")
            await asyncio.sleep(0.05)
            order.append("end")

        async def both():
            await asyncio.gather(js.run_one(self.job("t_slow"), self.factory), js.run_one(self.job("t_slow"), self.factory))

        asyncio.run(both())
        self.assertEqual(order, ["start", "end", "start", "end"])

    def test_every_queued_kind_has_a_handler(self):
        js.import_handlers()
        for kind in ("learn_from_message", "follow_ups", "people", "index_memories", "life_memory"):
            self.assertIn(kind, js._handlers, kind)


if __name__ == "__main__":
    unittest.main()
