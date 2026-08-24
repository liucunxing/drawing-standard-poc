import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from backend.app.services.nozzle_markdown_corrector import (
    LLMCorrectionConfig,
    correct_nozzle_table_md,
)
from backend.app.services.mineru_img2md import _should_apply_qwen_nozzle_fix


HEADER = (
    "<tr><td rowspan=1 colspan=1>管口号</td>"
    "<td rowspan=1 colspan=1>公称尺寸DN</td>"
    "<td rowspan=1 colspan=1>法兰标准</td>"
    "<td rowspan=1 colspan=1>法兰类型代号</td></tr>"
)


def make_document(dn: str, standard: str, flange_type: str, *, prefix: str = "# 管口表\n") -> str:
    row = (
        "<tr><td rowspan=1 colspan=1>N1</td>"
        f"<td rowspan=1 colspan=1>{dn}</td>"
        f"<td rowspan=1 colspan=1>{standard}</td>"
        f"<td rowspan=1 colspan=1>{flange_type}</td></tr>"
    )
    return prefix + "<table data-source=\"mineru\">" + HEADER + row + "</table>\n尾注保持不变"


class FakeCompletions:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.responder(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=10, total_tokens=130),
        )


class FakeClient:
    def __init__(self, responder):
        self.completions = FakeCompletions(responder)
        self.chat = SimpleNamespace(completions=self.completions)


def enabled_config(**overrides):
    values = {
        "enabled": True,
        "base_url": "http://127.0.0.1:9999/v1",
        "api_key": "EMPTY",
        "model": "qwen-test",
        "provider": "qwen-vllm",
        "disable_thinking": True,
        "max_output_tokens": 512,
        "timeout_seconds": 10.0,
        "max_retries": 0,
        "max_rows_per_request": 20,
    }
    values.update(overrides)
    return LLMCorrectionConfig(**values)


class NozzleMarkdownCorrectorTests(unittest.TestCase):
    def test_mineru_trigger_accepts_required_headers_without_table_title(self):
        source = make_document("50", "HG/T 20592-2009", "IF", prefix="")

        self.assertTrue(_should_apply_qwen_nozzle_fix(source))

    def test_document_without_target_table_is_unchanged(self):
        source = "# 普通表格\n<table><tr><td>A</td><td>B</td></tr></table>"

        result = correct_nozzle_table_md(source)

        self.assertFalse(result.changed)
        self.assertEqual(result.content, source)
        self.assertEqual(result.metrics.method, "skipped_no_target_table")

    def test_right_drift_is_repaired_without_llm(self):
        source = make_document("50", "HG/T 20592-200", "9 IF")
        client = FakeClient(lambda _: '{"patches":[]}')

        result = correct_nozzle_table_md(source, config=enabled_config(), client=client)

        self.assertTrue(result.changed)
        self.assertIn(">HG/T 20592-2009</td>", result.content)
        self.assertIn(">IF</td>", result.content)
        self.assertEqual(result.metrics.method, "rules")
        self.assertEqual(result.metrics.rule_fixes, 1)
        self.assertEqual(client.completions.calls, [])

    def test_left_drift_and_missing_h_are_repaired_without_llm(self):
        source = make_document("50 H", "G/T 20592-2009", "IF")

        result = correct_nozzle_table_md(source)

        self.assertIn(">50</td>", result.content)
        self.assertIn(">HG/T 20592-2009</td>", result.content)
        self.assertNotIn(">50 H</td>", result.content)
        self.assertEqual(result.metrics.method, "rules")

    def test_dual_drift_preserves_all_tags_and_unrelated_text(self):
        source = make_document("50 H", "G/T 20592-200", "9 IF", prefix="前言不可修改\n")
        expected = source.replace(">50 H</td>", ">50</td>").replace(
            ">G/T 20592-200</td>", ">HG/T 20592-2009</td>"
        ).replace(">9 IF</td>", ">IF</td>")

        result = correct_nozzle_table_md(source)

        self.assertEqual(result.content, expected)
        self.assertIn('<table data-source="mineru">', result.content)
        self.assertTrue(result.content.endswith("尾注保持不变"))
        self.assertEqual(result.metrics.patched_cells, 3)

    def test_ambiguous_row_uses_small_json_patch_and_disables_qwen_thinking(self):
        unrelated = "不会发送给模型的正文" * 1000
        source = make_document("50", "HG/T 20592-200", "9 内螺纹", prefix=unrelated + "\n")

        def responder(kwargs):
            user_prompt = kwargs["messages"][1]["content"]
            payload = json.loads(user_prompt.split("输入行（JSON）：\n", 1)[1])
            row = payload["rows"][0]
            return json.dumps(
                {
                    "patches": [
                        {
                            "row_id": row["row_id"],
                            "cells": {
                                "法兰标准": "HG/T 20592-2009",
                                "法兰类型代号": "内螺纹",
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            )

        client = FakeClient(responder)
        result = correct_nozzle_table_md(source, config=enabled_config(), client=client)

        self.assertTrue(result.changed)
        self.assertIn(">HG/T 20592-2009</td>", result.content)
        self.assertIn(">内螺纹</td>", result.content)
        self.assertEqual(result.metrics.method, "llm_patch")
        self.assertEqual(result.metrics.llm_requests, 1)
        self.assertEqual(result.metrics.llm_prompt_tokens, 120)
        self.assertEqual(result.metrics.llm_completion_tokens, 10)
        self.assertEqual(result.metrics.needs_review_rows, 0)

        call = client.completions.calls[0]
        sent_text = "".join(message["content"] for message in call["messages"])
        self.assertNotIn(unrelated, sent_text)
        self.assertLess(len(sent_text), len(source) / 5)
        self.assertEqual(call["max_tokens"], 512)
        self.assertEqual(
            call["extra_body"],
            {"chat_template_kwargs": {"enable_thinking": False}},
        )
        self.assertTrue(call["messages"][1]["content"].startswith("/no_think"))

    def test_hallucinated_patch_is_rejected_and_original_is_kept(self):
        source = make_document("50", "HG/T 20592-200", "9 内螺纹")

        def responder(kwargs):
            payload = json.loads(kwargs["messages"][1]["content"].split("输入行（JSON）：\n", 1)[1])
            return json.dumps(
                {
                    "patches": [
                        {
                            "row_id": payload["rows"][0]["row_id"],
                            "cells": {
                                "法兰标准": "HG/T 20592-2008",
                                "法兰类型代号": "内螺纹",
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            )

        result = correct_nozzle_table_md(
            source,
            config=enabled_config(),
            client=FakeClient(responder),
        )

        self.assertFalse(result.changed)
        self.assertEqual(result.content, source)
        self.assertEqual(result.metrics.method, "needs_review")
        self.assertEqual(result.metrics.needs_review_rows, 1)

    def test_missing_llm_configuration_fails_closed(self):
        source = make_document("50", "HG/T 20592-200", "9 内螺纹")
        config = enabled_config(base_url="", api_key="", model="")

        result = correct_nozzle_table_md(source, config=config)

        self.assertEqual(result.content, source)
        self.assertEqual(result.metrics.method, "needs_review")
        self.assertIn("missing_llm_base_url", result.metrics.llm_error_type)

    def test_real_openai_client_sends_bounded_request_to_compatible_endpoint(self):
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                request_payload = json.loads(body.decode("utf-8"))
                received["path"] = self.path
                received["payload"] = request_payload
                user_prompt = request_payload["messages"][1]["content"]
                row = json.loads(user_prompt.split("输入行（JSON）：\n", 1)[1])["rows"][0]
                response_payload = {
                    "id": "chatcmpl-local-test",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "qwen-test",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "patches": [
                                            {
                                                "row_id": row["row_id"],
                                                "cells": {
                                                    "法兰标准": "HG/T 20592-2009",
                                                    "法兰类型代号": "内螺纹",
                                                },
                                            }
                                        ]
                                    },
                                    ensure_ascii=False,
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 10,
                        "total_tokens": 110,
                    },
                }
                encoded = json.dumps(response_payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            source = make_document("50", "HG/T 20592-200", "9 内螺纹")
            config = enabled_config(base_url=f"http://127.0.0.1:{server.server_port}/v1")
            result = correct_nozzle_table_md(source, config=config)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertTrue(result.changed)
        self.assertEqual(received["path"], "/v1/chat/completions")
        payload = received["payload"]
        self.assertEqual(payload["max_tokens"], 512)
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
        self.assertNotIn("# 管口表", payload["messages"][1]["content"])
        self.assertEqual(result.metrics.llm_total_tokens, 110)

    def test_nested_target_cell_is_not_rewritten(self):
        source = make_document("<b>50 H</b>", "G/T 20592-2009", "IF")

        result = correct_nozzle_table_md(source)

        self.assertFalse(result.changed)
        self.assertEqual(result.content, source)
        self.assertEqual(result.metrics.method, "needs_review")

    def test_merged_target_cell_is_skipped_instead_of_guessing_column_alignment(self):
        source = make_document("50", "HG/T 20592-200", "9 IF").replace(
            "rowspan=1 colspan=1>50</td>",
            "rowspan=1 colspan=2>50</td>",
            1,
        )

        result = correct_nozzle_table_md(source)

        self.assertFalse(result.changed)
        self.assertEqual(result.content, source)
        self.assertEqual(result.metrics.method, "skipped_no_supported_rows")


if __name__ == "__main__":
    unittest.main()
