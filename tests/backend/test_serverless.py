"""Running on Vercel: no worker loop, jobs drained on request, a secret-protected tick,
and push keys that must come from the environment."""

import asyncio
import os
import unittest
import uuid
from unittest import mock

from app.services import job_service as js


class DrainTests(unittest.TestCase):
    def test_runs_claimed_batches_until_nothing_is_left(self):
        batches = [[{"id": 1, "user_id": "u"}, {"id": 2, "user_id": "u"}], [{"id": 3, "user_id": "u"}], []]
        claimed_for = []
        ran = []

        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        async def fake_claim(db, limit, user_id=None):
            claimed_for.append(user_id)
            return batches.pop(0)

        async def fake_run_one(job, factory):
            ran.append(job["id"])

        user = uuid.uuid4()
        with mock.patch.object(js, "claim", fake_claim), mock.patch.object(js, "run_one", fake_run_one), mock.patch.object(js, "import_handlers", lambda: None):
            count = asyncio.run(js.drain(Session, user_id=user, budget_seconds=5))
        self.assertEqual(count, 3)
        self.assertEqual(sorted(ran), [1, 2, 3])
        self.assertEqual(claimed_for, [user, user, user])  # only that person's jobs

    def test_stops_claiming_when_the_budget_is_spent(self):
        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        calls = []

        async def fake_claim(db, limit, user_id=None):
            calls.append(1)
            return [{"id": len(calls), "user_id": "u"}]

        async def slow_run_one(job, factory):
            await asyncio.sleep(0.05)

        with mock.patch.object(js, "claim", fake_claim), mock.patch.object(js, "run_one", slow_run_one), mock.patch.object(js, "import_handlers", lambda: None):
            count = asyncio.run(js.drain(Session, budget_seconds=0.12))
        self.assertLessEqual(count, 4)
        self.assertGreaterEqual(count, 1)


class WorkerSwitchTests(unittest.TestCase):
    def test_no_worker_loop_on_vercel_unless_asked(self):
        with mock.patch.dict(os.environ, {"VERCEL": "1"}, clear=False):
            os.environ.pop("REFLECTRA_WORKER", None)
            self.assertFalse(js.worker_enabled())
        with mock.patch.dict(os.environ, {"VERCEL": ""}, clear=False):
            os.environ.pop("REFLECTRA_WORKER", None)
            self.assertTrue(js.worker_enabled())
        with mock.patch.dict(os.environ, {"REFLECTRA_WORKER": "0", "VERCEL": ""}):
            self.assertFalse(js.worker_enabled())


class TickAuthTests(unittest.TestCase):
    def test_only_the_cron_secret_gets_in(self):
        from app.api.jobs import _authorized

        with mock.patch.dict(os.environ, {"CRON_SECRET": "s3cret-value"}):
            self.assertTrue(_authorized("Bearer s3cret-value"))
            self.assertFalse(_authorized("Bearer wrong"))
            self.assertFalse(_authorized("s3cret-value"))
            self.assertFalse(_authorized(None))
        with mock.patch.dict(os.environ, {"CRON_SECRET": ""}):
            self.assertFalse(_authorized("Bearer "))  # unset secret never opens it


class CronTests(unittest.TestCase):
    def test_vercel_cron_can_reach_the_tick(self):
        import json
        from pathlib import Path

        from app.api.jobs import internal_router

        methods = {m for route in internal_router.routes if route.path.endswith("/tick") for m in route.methods}
        self.assertTrue({"GET", "POST"} <= methods)  # Vercel's cron uses GET
        config = json.loads((Path(__file__).resolve().parents[2] / "vercel.json").read_text(encoding="utf-8"))
        self.assertIn({"path": "/api/internal/tick", "schedule": "0 13 * * *"}, config["crons"])


class DatabaseUrlTests(unittest.TestCase):
    def test_supabase_session_pooler_becomes_the_transaction_pooler(self):
        from app.db.database import serverless_database_url

        url = serverless_database_url("postgresql+asyncpg://postgres.abc:pw@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres")
        self.assertIn("pooler.supabase.com:6543/postgres", url)
        self.assertIn("prepared_statement_cache_size=0", url)
        self.assertIn(":pw@", url)  # credentials are kept, not masked

    def test_other_databases_keep_their_port(self):
        from app.db.database import serverless_database_url

        self.assertIn("db.example.com:5432", serverless_database_url("postgresql+asyncpg://u:p@db.example.com:5432/app"))
        already = serverless_database_url("postgresql+asyncpg://u:p@x.pooler.supabase.com:6543/postgres")
        self.assertIn(":6543/", already)


class PushKeyTests(unittest.TestCase):
    def test_on_vercel_keys_must_come_from_the_environment(self):
        from app.services import push_service as ps

        with mock.patch.object(ps, "_keys", None), mock.patch.object(ps, "KEY_FILE", ps.KEY_FILE.with_name("missing-vapid.json")):
            with mock.patch.dict(os.environ, {"VERCEL": "1", "VAPID_PUBLIC_KEY": "", "VAPID_PRIVATE_KEY": ""}):
                with self.assertRaises(RuntimeError):
                    ps.vapid_keys()
            with mock.patch.dict(os.environ, {"VERCEL": "1", "VAPID_PUBLIC_KEY": "pub", "VAPID_PRIVATE_KEY": "priv"}):
                self.assertEqual(ps.vapid_keys(), ("pub", "priv"))


if __name__ == "__main__":
    unittest.main()
