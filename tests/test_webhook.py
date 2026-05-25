import asyncio
import time
from typing import Optional

from fastapi.testclient import TestClient

from app.main import create_app


class DeterministicLLM:
    def __init__(self, should_fail: bool = False, delay_seconds: float = 0.1) -> None:
        self.should_fail = should_fail
        self.delay_seconds = delay_seconds

    async def generate_reply(self, user_message: str) -> str:
        await asyncio.sleep(self.delay_seconds)
        if self.should_fail:
            raise RuntimeError("simulated_llm_failure")
        return f"ok:{user_message}"


def wait_for_status(client: TestClient, message_id: str, expected: str, timeout: float = 2.0) -> dict:
    start = time.perf_counter()
    last_body: Optional[dict] = None

    while time.perf_counter() - start < timeout:
        response = client.get(f"/messages/{message_id}")
        assert response.status_code == 200
        body = response.json()
        last_body = body
        if body["status"] == expected:
            return body
        time.sleep(0.02)

    raise AssertionError(f"timeout waiting for status={expected}; last={last_body}")


def test_webhook_is_non_blocking_even_with_slow_llm() -> None:
    app = create_app(llm_client=DeterministicLLM(delay_seconds=1.0))

    with TestClient(app) as client:
        started = time.perf_counter()
        response = client.post(
            "/webhook",
            json={"user_id": "5511999999999", "message": "quero renegociar minha divida"},
        )
        elapsed = time.perf_counter() - started

        assert response.status_code == 202
        assert elapsed < 0.35


def test_success_flow_dispatches_outbound_message() -> None:
    app = create_app(llm_client=DeterministicLLM())

    with TestClient(app) as client:
        response = client.post(
            "/webhook",
            json={"user_id": "5511888887777", "message": "aceito proposta com entrada"},
        )
        assert response.status_code == 202

        message_id = response.json()["message_id"]
        status_body = wait_for_status(client, message_id, "sent")
        assert status_body["status"] == "sent"
        assert status_body["error"] is None

        outbound_response = client.get("/outbound-mock")
        assert outbound_response.status_code == 200
        outbound_items = outbound_response.json()
        assert len(outbound_items) == 1
        assert outbound_items[0]["message_id"] == message_id


def test_llm_failure_marks_message_as_failed() -> None:
    app = create_app(llm_client=DeterministicLLM(should_fail=True, delay_seconds=0.05))

    with TestClient(app) as client:
        response = client.post(
            "/webhook",
            json={"user_id": "5511777776666", "message": "nao consigo pagar hoje"},
        )
        assert response.status_code == 202

        message_id = response.json()["message_id"]
        status_body = wait_for_status(client, message_id, "failed")
        assert status_body["error"] == "simulated_llm_failure"

        outbound_response = client.get("/outbound-mock")
        assert outbound_response.status_code == 200
        assert outbound_response.json() == []
