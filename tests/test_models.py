"""P1.1: GMBackend adapters, pricing, and the billing toggle.

No network, no API key, no GPU. The `api` adapter is exercised through a fake client
that records the payload — which is the part worth pinning, since the documented ways to
break a request on Sonnet 5 / Opus 5 are all *request-construction* mistakes.
"""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from dndc.config import Billing, load_config, save_billing_default
from dndc.models import (
    APIBackend,
    GMBackendError,
    GMRequest,
    Message,
    MockBackend,
    OllamaBackend,
    Role,
    SubscriptionBackend,
    Usage,
    build_gm_backend,
    build_npc_backend,
    estimate_cost,
    load_prices,
    price_for,
    to_messages,
)
from dndc.models.api import FALLBACK_BETA
from dndc.models.pricing import ModelPrice
from dndc.models.subscription import METERED_ENV_VARS


def request(**overrides) -> GMRequest:
    data = {
        "system": "You are the GM.",
        "messages": (Message(role=Role.USER, content="I open the door."),),
        "max_tokens": 512,
    }
    data.update(overrides)
    return GMRequest(**data)


# --- fake anthropic client -------------------------------------------------


class FakeStream:
    def __init__(self, message, chunks):
        self._message = message
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        return iter(self._chunks)

    def get_final_message(self):
        return self._message


class FakeMessages:
    def __init__(self, message, chunks):
        self.message = message
        self.chunks = chunks
        self.payloads: list[dict] = []

    def stream(self, **payload):
        self.payloads.append(payload)
        return FakeStream(self.message, self.chunks)


class FakeClient:
    def __init__(self, message, chunks=("Hello",)):
        self.messages = FakeMessages(message, chunks)
        self.beta = SimpleNamespace(messages=self.messages)
        self.closed = False

    def close(self):
        self.closed = True


def message(
    text="The door groans open.",
    stop_reason="end_turn",
    model="claude-sonnet-5",
    usage=None,
    stop_details=None,
):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        model=model,
        stop_details=stop_details,
        usage=usage
        or SimpleNamespace(
            input_tokens=120,
            output_tokens=45,
            cache_read_input_tokens=900,
            cache_creation_input_tokens=0,
        ),
    )


# --- api adapter: request construction -------------------------------------


def test_api_never_sends_sampling_parameters():
    """temperature / top_p / top_k are a 400 on Sonnet 5 and Opus 5."""
    client = FakeClient(message())
    APIBackend(model="claude-sonnet-5", client=client).generate(request())
    payload = client.messages.payloads[0]
    assert "temperature" not in payload
    assert "top_p" not in payload
    assert "top_k" not in payload


def test_api_never_sends_budget_tokens():
    """Manual extended thinking is removed; depth is output_config.effort."""
    client = FakeClient(message())
    APIBackend(model="claude-sonnet-5", client=client).generate(request())
    assert "thinking" not in client.messages.payloads[0]


def test_api_caches_the_system_prefix():
    """The GM prompt is large and rebuilt every turn — that is what caching pays for."""
    client = FakeClient(message())
    APIBackend(model="claude-sonnet-5", client=client).generate(request())
    system = client.messages.payloads[0]["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_volatile_state_is_a_second_uncached_block():
    """P1.2: campaign state must sit outside the breakpoint, or a hit point of damage
    invalidates the cached copy of the whole instruction set."""
    client = FakeClient(message())
    APIBackend(model="claude-sonnet-5", client=client).generate(
        request(system_volatile="## Established canon\n- The bridge is rotting.")
    )
    system = client.messages.payloads[0]["system"]

    assert len(system) == 2
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in system[1]
    assert "bridge is rotting" in system[1]["text"]


def test_no_volatile_block_is_sent_when_there_is_no_state():
    client = FakeClient(message())
    APIBackend(model="claude-sonnet-5", client=client).generate(request())
    assert len(client.messages.payloads[0]["system"]) == 1


def test_caching_can_be_turned_off():
    client = FakeClient(message())
    APIBackend(model="claude-sonnet-5", client=client).generate(
        request(cache_system=False)
    )
    assert "cache_control" not in client.messages.payloads[0]["system"][0]


def test_effort_goes_inside_output_config():
    client = FakeClient(message())
    APIBackend(model="claude-sonnet-5", client=client).generate(request(effort="high"))
    assert client.messages.payloads[0]["output_config"] == {"effort": "high"}


def test_effort_is_omitted_when_unset():
    client = FakeClient(message())
    APIBackend(model="claude-sonnet-5", client=client).generate(request())
    assert "output_config" not in client.messages.payloads[0]


def test_request_model_overrides_the_seat_default():
    client = FakeClient(message())
    APIBackend(model="claude-sonnet-5", client=client).generate(
        request(model="claude-opus-5")
    )
    assert client.messages.payloads[0]["model"] == "claude-opus-5"


def test_messages_are_translated_to_the_wire_shape():
    client = FakeClient(message())
    history = to_messages([("user", "I knock."), ("assistant", "Silence."), ("user", "Again.")])
    APIBackend(model="claude-sonnet-5", client=client).generate(request(messages=history))
    assert client.messages.payloads[0]["messages"] == [
        {"role": "user", "content": "I knock."},
        {"role": "assistant", "content": "Silence."},
        {"role": "user", "content": "Again."},
    ]


# --- api adapter: refusals and fallbacks -----------------------------------


def test_refusal_is_flagged_rather_than_trusted_as_text():
    """A declined request is HTTP 200 with empty content — not an exception."""
    refused = message(text="", stop_reason="refusal",
                      stop_details=SimpleNamespace(category="cyber"))
    client = FakeClient(refused, chunks=())
    response = APIBackend(model="claude-sonnet-5", client=client).generate(request())
    assert response.refused is True
    assert response.refusal_category == "cyber"
    assert response.text == ""


def test_normal_response_is_not_flagged_as_refused():
    client = FakeClient(message())
    response = APIBackend(model="claude-sonnet-5", client=client).generate(request())
    assert response.refused is False
    assert response.text == "The door groans open."


def test_fallbacks_are_enabled_for_models_that_can_refuse():
    client = FakeClient(message())
    APIBackend(model="claude-opus-5", client=client).generate(request())
    payload = client.messages.payloads[0]
    assert payload["fallbacks"] == "default"
    assert payload["betas"] == [FALLBACK_BETA]


def test_fallbacks_can_be_disabled():
    client = FakeClient(message())
    APIBackend(model="claude-opus-5", client=client, use_fallbacks=False).generate(request())
    assert "fallbacks" not in client.messages.payloads[0]


@pytest.mark.parametrize("model", ["claude-sonnet-5", "claude-haiku-4-5", "claude-opus-4-8"])
def test_fallbacks_are_not_sent_to_models_that_reject_the_parameter(model):
    """Verified against the live API: sonnet-5 returns 400 on `fallbacks`."""
    client = FakeClient(message(model=model))
    APIBackend(model=model, client=client).generate(request())
    payload = client.messages.payloads[0]
    assert "fallbacks" not in payload
    assert "betas" not in payload


# --- api adapter: streaming and usage --------------------------------------


def test_streamed_text_reaches_the_callback():
    client = FakeClient(message(), chunks=("The door ", "groans ", "open."))
    seen: list[str] = []
    APIBackend(model="claude-sonnet-5", client=client).generate(request(), on_text=seen.append)
    assert "".join(seen) == "The door groans open."


def test_usage_captures_all_four_token_counts():
    client = FakeClient(message())
    response = APIBackend(model="claude-sonnet-5", client=client).generate(request())
    assert response.usage == Usage(
        input_tokens=120, output_tokens=45, cache_read_tokens=900, cache_write_tokens=0
    )
    assert response.usage.total_tokens == 1065


def test_every_call_gets_a_correlation_id():
    """OD-9: pending and terminal writes of one call share this."""
    client = FakeClient(message())
    backend = APIBackend(model="claude-sonnet-5", client=client)
    first = backend.generate(request())
    second = backend.generate(request())
    assert first.call_id and second.call_id
    assert first.call_id != second.call_id


def test_close_releases_the_client():
    client = FakeClient(message())
    backend = APIBackend(model="claude-sonnet-5", client=client)
    backend.close()
    assert client.closed is True


def test_missing_api_key_explains_the_alternative(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(GMBackendError, match="subscription"):
        APIBackend(model="claude-sonnet-5")


# --- subscription adapter: the auth trap -----------------------------------


def _completed(payload: dict, returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=json.dumps(payload), stderr=stderr
    )


SUB_PAYLOAD = {
    "is_error": False,
    "subtype": "success",
    "result": "The tavern falls quiet.",
    "stop_reason": "end_turn",
    "total_cost_usd": 0.0104789,
    "duration_ms": 2134,
    "usage": {
        "input_tokens": 2,
        "output_tokens": 4,
        "cache_read_input_tokens": 32773,
        "cache_creation_input_tokens": 0,
    },
}


def test_subscription_strips_metered_credentials_from_the_child(monkeypatch):
    """Otherwise 'subscription mode' silently bills the API key (verified 2026-08-04)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-leak")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "should-not-leak-either")
    monkeypatch.setenv("PATH_MARKER", "kept")

    env = SubscriptionBackend(model="claude-sonnet-5").child_env()
    for name in METERED_ENV_VARS:
        assert name not in env
    assert env["PATH_MARKER"] == "kept"


def test_subscription_can_pin_an_explicit_auth_token(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-leak")
    env = SubscriptionBackend(model="m", auth_token="oauth-token").child_env()
    assert env["ANTHROPIC_AUTH_TOKEN"] == "oauth-token"
    assert "ANTHROPIC_API_KEY" not in env


def test_subscription_command_shape():
    backend = SubscriptionBackend(model="claude-sonnet-5")
    command = backend.command(request())
    assert command[:2] == ["claude", "-p"]
    assert "--output-format" in command and "json" in command
    assert command[command.index("--model") + 1] == "claude-sonnet-5"
    # Replace rather than append: the GM persona is the whole system prompt.
    assert "--system-prompt" in command
    assert "--append-system-prompt" not in command


def test_subscription_collapses_both_system_halves():
    """Headless CC takes one prompt string, so the cache-split has nothing to attach to
    here — but the campaign state must still arrive."""
    backend = SubscriptionBackend(model="claude-sonnet-5")
    command = backend.command(request(system_volatile="The bridge is rotting."))
    sent = command[command.index("--system-prompt") + 1]
    assert "You are the GM." in sent
    assert "The bridge is rotting." in sent


def test_subscription_parses_the_real_output_shape():
    captured = {}

    def runner(command, **kwargs):
        captured.update(kwargs)
        return _completed(SUB_PAYLOAD)

    response = SubscriptionBackend(model="claude-sonnet-5", runner=runner).generate(request())
    assert response.text == "The tavern falls quiet."
    assert response.usage.cache_read_tokens == 32773
    assert response.reported_usd == pytest.approx(0.0104789)
    assert response.duration_ms == 2134
    assert "ANTHROPIC_API_KEY" not in captured["env"]


def test_subscription_tolerates_a_warning_before_the_json():
    """Claude Code prints warnings to stdout; the JSON is still in there."""
    noisy = subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout="⚠ some warning about connectors\n" + json.dumps(SUB_PAYLOAD),
        stderr="",
    )
    response = SubscriptionBackend(
        model="m", runner=lambda *a, **k: noisy
    ).generate(request())
    assert response.text == "The tavern falls quiet."


def test_subscription_reports_a_nonzero_exit():
    failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")
    with pytest.raises(GMBackendError, match="exited 1"):
        SubscriptionBackend(model="m", runner=lambda *a, **k: failed).generate(request())


def test_subscription_reports_an_error_payload():
    payload = dict(SUB_PAYLOAD, is_error=True, result="rate limited")
    with pytest.raises(GMBackendError, match="rate limited"):
        SubscriptionBackend(
            model="m", runner=lambda *a, **k: _completed(payload)
        ).generate(request())


def test_subscription_reports_a_timeout():
    def runner(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)

    with pytest.raises(GMBackendError, match="timed out"):
        SubscriptionBackend(model="m", runner=runner).generate(request())


def test_subscription_rejects_unparseable_output():
    garbage = subprocess.CompletedProcess(args=[], returncode=0, stdout="not json", stderr="")
    with pytest.raises(GMBackendError, match="could not parse"):
        SubscriptionBackend(model="m", runner=lambda *a, **k: garbage).generate(request())


def test_multi_turn_history_is_labelled_for_a_single_prompt_string():
    backend = SubscriptionBackend(model="m")
    history = to_messages([("user", "I knock."), ("assistant", "Silence."), ("user", "Again.")])
    prompt = backend.command(request(messages=history))[2]
    assert "Player: I knock." in prompt
    assert "GM: Silence." in prompt


def test_single_user_turn_is_passed_through_verbatim():
    backend = SubscriptionBackend(model="m")
    assert backend.command(request())[2] == "I open the door."


# --- ollama adapter --------------------------------------------------------


class FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def test_ollama_payload_puts_system_first():
    captured = {}

    def opener(http_request, timeout=None):
        captured["url"] = http_request.full_url
        captured["body"] = json.loads(http_request.data)
        return FakeHTTPResponse(
            {"message": {"content": "hm."}, "model": "llama3.3:70b",
             "prompt_eval_count": 11, "eval_count": 3, "done_reason": "stop"}
        )

    backend = OllamaBackend(
        model="llama3.3:70b", endpoint="http://192.168.50.11:11434", opener=opener
    )
    response = backend.generate(request())

    assert captured["url"] == "http://192.168.50.11:11434/api/chat"
    assert captured["body"]["messages"][0]["role"] == "system"
    assert captured["body"]["stream"] is False
    assert response.usage.input_tokens == 11
    assert response.usage.output_tokens == 3
    assert response.reported_usd == 0.0  # local inference is free, not unknown


def test_ollama_merges_both_system_halves_into_one_message():
    captured = {}

    def opener(http_request, timeout=None):
        captured["body"] = json.loads(http_request.data)
        return FakeHTTPResponse(
            {"message": {"content": "hm."}, "model": "llama3.3:70b",
             "prompt_eval_count": 11, "eval_count": 3, "done_reason": "stop"}
        )

    backend = OllamaBackend(
        model="llama3.3:70b", endpoint="http://192.168.50.11:11434", opener=opener
    )
    backend.generate(request(system_volatile="The bridge is rotting."))

    system = captured["body"]["messages"][0]
    assert system["role"] == "system"
    assert "You are the GM." in system["content"]
    assert "The bridge is rotting." in system["content"]


def test_ollama_unreachable_endpoint_names_the_host():
    import urllib.error

    def opener(*a, **k):
        raise urllib.error.URLError("connection refused")

    backend = OllamaBackend(model="m", endpoint="http://192.168.50.11:11434", opener=opener)
    with pytest.raises(GMBackendError, match="192.168.50.11"):
        backend.generate(request())


# --- mock backend ----------------------------------------------------------


def test_mock_records_requests_and_replays_responses():
    backend = MockBackend(responses=["first", "second"])
    assert backend.generate(request()).text == "first"
    assert backend.generate(request()).text == "second"
    assert len(backend.calls) == 2
    assert backend.last_request.system == "You are the GM."


def test_mock_repeats_its_last_response_by_default():
    backend = MockBackend(responses=["only"])
    backend.generate(request())
    assert backend.generate(request()).text == "only"


def test_mock_can_be_made_strict():
    backend = MockBackend(responses=["only"], repeat_last=False)
    backend.generate(request())
    with pytest.raises(GMBackendError, match="ran out of scripted"):
        backend.generate(request())


def test_mock_streams_to_the_callback():
    seen: list[str] = []
    MockBackend(responses=["narration"]).generate(request(), on_text=seen.append)
    assert seen == ["narration"]


# --- pricing ---------------------------------------------------------------


PRICES = {
    "claude-sonnet-5": ModelPrice(input=3.0, output=15.0),
    "claude-opus-5": ModelPrice(input=5.0, output=25.0),
}


def test_cost_uses_all_four_token_classes():
    usage = Usage(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_write_tokens=1_000_000,
        cache_read_tokens=1_000_000,
    )
    # 3.00 input + 15.00 output + 3.75 write (1.25x) + 0.30 read (0.1x)
    assert estimate_cost(usage, "claude-sonnet-5", PRICES) == pytest.approx(22.05)


def test_cache_reads_are_a_tenth_of_input():
    usage = Usage(cache_read_tokens=1_000_000)
    assert estimate_cost(usage, "claude-sonnet-5", PRICES) == pytest.approx(0.30)


def test_explicit_cache_rates_win_over_the_derived_ones():
    prices = {"m": ModelPrice(input=10.0, output=10.0, cache_write=1.0, cache_read=0.5)}
    usage = Usage(cache_write_tokens=1_000_000, cache_read_tokens=1_000_000)
    assert estimate_cost(usage, "m", prices) == pytest.approx(1.5)


def test_an_unpriced_model_yields_none_rather_than_a_guess():
    """A wrong number in the cost log is worse than a missing one (Phase 7 reads it)."""
    assert estimate_cost(Usage(input_tokens=1000), "some-new-model", PRICES) is None


def test_dated_snapshot_ids_resolve_to_their_base_price():
    assert price_for("claude-sonnet-5-20260115", PRICES) is PRICES["claude-sonnet-5"]


def test_longest_prefix_wins():
    prices = {"claude": ModelPrice(input=1, output=1),
              "claude-opus-5": ModelPrice(input=5, output=25)}
    assert price_for("claude-opus-5-preview", prices).input == 5


def test_prices_load_from_the_real_config():
    cfg = load_config()
    prices = load_prices(cfg.pricing)
    assert prices["claude-sonnet-5"].input > 0
    assert prices["claude-opus-5"].output > prices["claude-sonnet-5"].output


# --- backend selection -----------------------------------------------------


def test_billing_choice_selects_the_adapter(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    cfg = load_config()
    assert build_gm_backend(cfg, Billing.API).name == "api"
    assert build_gm_backend(cfg, Billing.SUBSCRIPTION).name == "subscription"


def test_threshold_selects_the_escalation_model():
    """OD-3: Opus only at authored threshold moments."""
    cfg = load_config()
    default = build_gm_backend(cfg, Billing.SUBSCRIPTION)
    escalated = build_gm_backend(cfg, Billing.SUBSCRIPTION, threshold=True)
    assert default.model == cfg.seats.gm.model_default
    assert escalated.model == cfg.seats.gm.model_threshold
    assert default.model != escalated.model


def test_seats_come_from_config_not_from_code():
    cfg = load_config()
    npc = build_npc_backend(cfg)
    assert npc.model == cfg.seats.npc.model
    assert npc.endpoint == cfg.seats.npc.endpoint


# --- sticky billing default ------------------------------------------------


def test_sticky_default_rewrites_only_the_billing_line(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "billing:\n"
        "  default: api            # a comment worth keeping\n"
        "seats:\n"
        "  gm:\n"
        "    model_default: claude-sonnet-5\n",
        encoding="utf-8",
    )
    assert save_billing_default(Billing.SUBSCRIPTION, config) is True

    text = config.read_text(encoding="utf-8")
    assert "default: subscription" in text
    assert "# a comment worth keeping" in text  # comments survive; no yaml round-trip
    assert "model_default: claude-sonnet-5" in text


def test_sticky_default_is_a_noop_when_unchanged(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("billing:\n  default: api\n", encoding="utf-8")
    assert save_billing_default(Billing.API, config) is False
