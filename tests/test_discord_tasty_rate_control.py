import asyncio
import ast
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from modules import tasty_handler
from modules.tasty_rest_control import SharedRestGate


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def build_gate(tmp_path, clock):
    return SharedRestGate(
        lock_path=tmp_path / "gate.lock",
        state_path=tmp_path / "gate.json",
        min_interval_seconds=2.0,
        base_backoff_seconds=60.0,
        max_backoff_seconds=300.0,
        clock=clock,
        sleeper=clock.sleep,
    )


class SharedRestGateTests(unittest.TestCase):
    def test_shared_gate_paces_independent_instances(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            clock = FakeClock()
            first = build_gate(Path(temp_dir), clock)
            second = build_gate(Path(temp_dir), clock)

            self.assertEqual(first.wait(), 0.0)
            self.assertEqual(second.wait(), 2.0)
            self.assertEqual(second.snapshot()["last_request_at"], 102.0)

    def test_shared_gate_publishes_exponential_429_backoff(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            clock = FakeClock()
            first = build_gate(Path(temp_dir), clock)
            second = build_gate(Path(temp_dir), clock)

            self.assertEqual(first.report_rate_limit(), 60.0)
            self.assertEqual(second.report_rate_limit(), 120.0)
            state = first.snapshot()
            self.assertEqual(state["consecutive_429"], 2)
            self.assertEqual(state["backoff_until"], 220.0)

            self.assertEqual(second.wait(), 120.0)
            second.report_success()
            self.assertEqual(first.snapshot()["consecutive_429"], 0)


class ChainCacheTests(unittest.TestCase):
    def tearDown(self):
        tasty_handler.clear_chain_cache()

    def test_nested_option_chain_is_reused_from_process_cache(self):
        chain = object()
        calls = []
        waits = []

        async def fake_get(session, ticker):
            calls.append((session, ticker))
            return [chain]

        async def fake_wait():
            waits.append(True)
            return 0.0

        tasty_handler.clear_chain_cache()
        session = object()
        with (
            mock.patch.object(tasty_handler.NestedOptionChain, "get", fake_get),
            mock.patch.object(tasty_handler, "wait_for_rest_slot", fake_wait),
            mock.patch.object(tasty_handler, "report_rest_success", lambda: None),
        ):
            self.assertIs(
                asyncio.run(tasty_handler.get_chain_async(session, "SPY")), chain
            )
            self.assertIs(
                asyncio.run(tasty_handler.get_chain_async(session, "SPY")), chain
            )

        self.assertEqual(calls, [(session, "SPY")])
        self.assertEqual(waits, [True])

    def test_nested_429_is_published_to_global_gate(self):
        published = []

        async def fake_get(session, ticker):
            raise RuntimeError("429 Too Many Requests")

        async def fake_wait():
            return 0.0

        tasty_handler.clear_chain_cache()
        with (
            mock.patch.object(tasty_handler.NestedOptionChain, "get", fake_get),
            mock.patch.object(tasty_handler, "wait_for_rest_slot", fake_wait),
            mock.patch.object(
                tasty_handler,
                "report_rest_rate_limit",
                lambda: published.append(True) or 60.0,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "429"):
                asyncio.run(tasty_handler.get_chain_async(object(), "QQQ"))

        self.assertEqual(published, [True])


class SchedulerPolicyTests(unittest.TestCase):
    def test_0dte_keeps_three_minute_cadence_and_slow_jobs_are_staggered(self):
        source = Path("discord_app/discord_send_plots.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        assignments = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"FAST_0DTE_CRON", "SLOW_JOB_CRONS"}
        }

        self.assertEqual(assignments["FAST_0DTE_CRON"], "0-59/3 3-16 * * 0-4")
        self.assertEqual(
            assignments["SLOW_JOB_CRONS"],
            {
                "1dte": "1,16,31,46 3-16 * * 0-4",
                "weekly": "8,38 3-16 * * 0-4",
            },
        )


if __name__ == "__main__":
    unittest.main()
