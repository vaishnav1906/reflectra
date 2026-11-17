"""Streaming replies: what is shown while a reply is written, and when it is taken back."""

import asyncio
import unittest
from unittest.mock import patch

from app.services import llm


def run(coro):
    return asyncio.run(coro)


def fake_stream(pieces, fail_after=None, delay=0.0):
    async def stream(model_name, messages, max_tokens, temperature):
        for index, piece in enumerate(pieces):
            if fail_after is not None and index == fail_after:
                raise RuntimeError("connection dropped")
            if delay:
                await asyncio.sleep(delay)
            yield piece

    return stream


class Collector:
    def __init__(self):
        self.events = []
        self.sink = llm.StreamSink(self.events.append)

    @property
    def shown(self):
        return [event["text"] for event in self.events if event["type"] == "partial"]

    @property
    def resets(self):
        return sum(1 for event in self.events if event["type"] == "reset")


async def stream_with(sink, **kwargs):
    token = llm.stream_sink.set(sink)
    try:
        return await llm.chat_complete_streaming([{"role": "user", "content": "hi"}], max_tokens=50, temperature=0.5, **kwargs)
    finally:
        llm.stream_sink.reset(token)


class StreamingTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(llm, "active_provider", return_value="gemini")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_without_an_open_stream_it_is_plain_chat_complete(self):
        async def plain(messages, **kwargs):
            return "plain answer"

        with patch.object(llm, "chat_complete", plain):
            self.assertEqual(run(llm.chat_complete_streaming([], max_tokens=10, temperature=0)), "plain answer")

    def test_text_is_shown_as_it_grows_and_returned_whole(self):
        collector = Collector()
        with patch.object(llm, "_gemini_stream", fake_stream(["yo ", "that ", "sounds rough"])):
            reply = run(stream_with(collector.sink))
        self.assertEqual(reply, "yo that sounds rough")
        self.assertEqual(collector.shown, ["yo ", "yo that ", "yo that sounds rough"])
        self.assertEqual(collector.resets, 0)

    def test_display_cleans_what_is_shown_but_not_what_is_returned(self):
        collector = Collector()
        with patch.object(llm, "_gemini_stream", fake_stream(["**Honestly** ", "same"])):
            reply = run(stream_with(collector.sink, display=lambda text: text.replace("*", "")))
        self.assertEqual(collector.shown[-1], "Honestly same")
        self.assertEqual(reply, "**Honestly** same")

    def test_a_draft_that_turns_robotic_is_taken_back_and_nothing_more_is_shown(self):
        collector = Collector()
        pieces = ["ok so ", "I understand how you feel. ", "As an AI ", "I think"]
        with patch.object(llm, "_gemini_stream", fake_stream(pieces)):
            reply = run(stream_with(collector.sink, reject_if=lambda text: "I understand how you feel" in text))
        self.assertEqual(collector.shown, ["ok so "])
        self.assertEqual(collector.resets, 1)
        self.assertIn("As an AI", reply)  # the caller still gets the whole draft to judge

    def test_slow_primary_model_falls_through_to_the_backup(self):
        calls = []

        async def stream(model_name, messages, max_tokens, temperature):
            calls.append(model_name)
            if len(calls) == 1:
                await asyncio.sleep(5)
            yield "quick answer"

        collector = Collector()
        with patch.object(llm, "_gemini_stream", stream), patch.dict("os.environ", {"GEMINI_STREAM_HEDGE_SECONDS": "0.05"}):
            reply = run(stream_with(collector.sink))
        self.assertEqual(reply, "quick answer")
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0], calls[1])

    def test_a_stream_that_breaks_mid_reply_is_taken_back_and_answered_the_plain_way(self):
        async def plain(messages, **kwargs):
            return "full answer from the fallback"

        collector = Collector()
        with patch.object(llm, "_gemini_stream", fake_stream(["half an ", "answer"], fail_after=1)), patch.object(llm, "chat_complete", plain):
            reply = run(stream_with(collector.sink))
        self.assertEqual(reply, "full answer from the fallback")
        self.assertEqual(collector.shown, ["half an "])
        self.assertEqual(collector.resets, 1)

    def test_rate_limit_still_surfaces_as_busy(self):
        async def never(model_name, messages, max_tokens, temperature):
            raise llm._ModelUnavailable("HTTP 429")
            yield ""  # pragma: no cover

        async def busy(messages, **kwargs):
            raise llm.LLMRateLimited("all busy")

        collector = Collector()
        with patch.object(llm, "_gemini_stream", never), patch.object(llm, "chat_complete", busy):
            with self.assertRaises(llm.LLMRateLimited):
                run(stream_with(collector.sink))
        self.assertEqual(collector.events, [])

    def test_reset_is_silent_when_nothing_was_shown(self):
        collector = Collector()
        collector.sink.reset()
        self.assertEqual(collector.events, [])


class StreamEndpointTests(unittest.TestCase):
    def test_route_exists_and_requires_login(self):
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            response = client.post("/chat/stream", json={"message": "hi", "mode": "reflection"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
