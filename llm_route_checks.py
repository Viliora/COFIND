"""Unit test: probe route rekomendasi + anti-spam log HF fallback."""
import unittest
from unittest.mock import MagicMock, patch

import llm_backend
from llm_backend import (
    LlmRunRoute,
    _chat_with_fallback,
    begin_llm_run_route,
    probe_llm_for_recommendation_run,
    reset_llm_run_route,
    set_llm_run_route,
)


def _mock_chat_response(content="ok"):
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    resp.usage = None
    return resp


class LlmRouteProbeTests(unittest.TestCase):
    def test_probe_both_fail_off(self):
        token = begin_llm_run_route()
        try:
            with patch.object(llm_backend, "hf_client", MagicMock()):
                with patch.object(llm_backend, "gemini_client", MagicMock()):
                    with patch.object(
                        llm_backend,
                        "_probe_provider_once",
                        side_effect=[(False, "Error code: 402"), (False, "invalid key")],
                    ):
                        route = probe_llm_for_recommendation_run()
            self.assertEqual(route.mode, "off")
            self.assertIn("gemini", route.reason)
        finally:
            reset_llm_run_route(token)

    def test_probe_hf_fail_gemini_ok(self):
        token = begin_llm_run_route()
        try:
            with patch.object(llm_backend, "hf_client", MagicMock()):
                with patch.object(llm_backend, "gemini_client", MagicMock()):
                    with patch.object(
                        llm_backend,
                        "_probe_provider_once",
                        side_effect=[(False, "Error code: 402 payment"), (True, None)],
                    ):
                        route = probe_llm_for_recommendation_run()
            self.assertEqual(route.mode, "gemini")
        finally:
            reset_llm_run_route(token)


class LlmRouteChatAntiSpamTests(unittest.TestCase):
    def test_gemini_route_skips_hf_without_warning(self):
        token = begin_llm_run_route()
        try:
            set_llm_run_route(
                LlmRunRoute(
                    mode="gemini",
                    reason="test",
                    probed_at=0.0,
                )
            )
            with patch.object(llm_backend, "hf_client", MagicMock()):
                with patch.object(llm_backend, "gemini_client", MagicMock()):
                    with patch.object(
                        llm_backend,
                        "_create_chat_completion",
                        return_value=_mock_chat_response("hi"),
                    ) as create:
                        with patch.object(llm_backend.logger, "warning") as warn:
                            for _ in range(3):
                                _chat_with_fallback(
                                    hf_model="test-model",
                                    messages=[{"role": "user", "content": "x"}],
                                    max_tokens=16,
                                    temperature=0.0,
                                    top_p=0.9,
                                    usage_stage="test",
                                )
                            for call in create.call_args_list:
                                self.assertEqual(call.kwargs.get("provider"), "gemini")
                            warn.assert_not_called()
        finally:
            reset_llm_run_route(token)

    def test_unset_route_warns_each_hf_failure(self):
        token = begin_llm_run_route()
        try:
            with patch.object(llm_backend, "hf_client", MagicMock()):
                with patch.object(llm_backend, "gemini_client", MagicMock()):
                    with patch.object(
                        llm_backend,
                        "_create_chat_completion",
                        side_effect=[
                            Exception("Error code: 402"),
                            _mock_chat_response("ok"),
                        ],
                    ):
                        with patch.object(llm_backend.logger, "warning") as warn:
                            _chat_with_fallback(
                                hf_model="test-model",
                                messages=[{"role": "user", "content": "x"}],
                                max_tokens=16,
                                temperature=0.0,
                                top_p=0.9,
                                usage_stage="test",
                            )
                            self.assertEqual(warn.call_count, 1)
        finally:
            reset_llm_run_route(token)


if __name__ == "__main__":
    unittest.main()
