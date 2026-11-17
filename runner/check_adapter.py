"""Offline regression checks for the third-party API adapter; no real model calls."""
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
import httpx
import openai
from configure import ROOT, REPO

os.chdir(REPO)
sys.path.insert(0, str(REPO))
from ufo.llm.openai import OpenAIService
from config.config_schemas import AgentConfig

agent = dict(API_TYPE="openai", API_BASE="https://example.invalid/v4", API_KEY="test",
             API_MODEL="glm-4.6v-flash", JSON_SCHEMA=False, FORCE_JSON_OUTPUT=True, DISABLE_MODEL_THINKING=True)
agent = AgentConfig.from_dict(agent).to_dict()
assert agent["FORCE_JSON_OUTPUT"] and agent["DISABLE_MODEL_THINKING"]
config = dict(HOST_AGENT=agent, MAX_RETRY=0, TIMEOUT=60, TEMPERATURE=0.1,
              MAX_TOKENS=2000, TOP_P=0.8)
response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2),
    choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])
client = Mock()
client.chat.completions.create.return_value = response
with patch.object(OpenAIService, "get_openai_client", return_value=client):
    service = OpenAIService(config, "HOST_AGENT")
    client.beta.chat.completions.parse.assert_not_called()
    content, _ = service.chat_completion([{"role": "user", "content": "Return JSON"}], 1)
    assert content == ['{"ok":true}']
    sent = client.chat.completions.create.call_args.kwargs
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["extra_body"] == {"thinking": {"type": "disabled"}}
    agent["RATE_LIMIT_BACKOFF"] = [10, 20]
    overloaded = openai.RateLimitError("overloaded", response=httpx.Response(429,
        request=httpx.Request("POST", "https://example.invalid/v4/chat/completions")),
        body={"code": "1305"})
    client.chat.completions.create.reset_mock()
    client.chat.completions.create.side_effect = [overloaded, response]
    with patch("ufo.llm.openai.time.sleep") as sleep:
        content, _ = service.chat_completion([{"role": "user", "content": "Return JSON"}], 1)
        sleep.assert_called_once_with(10)
        assert client.chat.completions.create.call_count == 2
agent["API_MODEL"] = "qwen3-vl-plus"
client.chat.completions.create.side_effect = None
with patch.object(OpenAIService, "get_openai_client", return_value=client):
    service = OpenAIService(config, "HOST_AGENT")
    service.chat_completion([{"role": "user", "content": "Return JSON"}], 1)
    assert client.chat.completions.create.call_args.kwargs["extra_body"] == {"enable_thinking": False}
report = dict(kind="offline_adapter_regression", passed=True,
              checks=["disabled_schema_probe_skipped", "json_mode_sent", "thinking_disabled", "content_preserved", "bounded_overload_backoff", "qwen_thinking_disabled"])
(ROOT / "logs/adapter_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
