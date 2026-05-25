from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, status

from .llm import LLMClient
from .schemas import EnqueueResponse, MessageStatusResponse, WebhookPayload
from .processor import InMemoryStore, MessageProcessor, OutboundGateway


def create_app(
    llm_client: Optional[LLMClient] = None,
    outbound_gateway: Optional[OutboundGateway] = None,
) -> FastAPI:
    store = InMemoryStore()
    processor = MessageProcessor(
        store=store,
        llm_client=llm_client,
        outbound_gateway=outbound_gateway,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = store
        app.state.processor = processor
        await processor.start()
        yield
        await processor.stop()

    app = FastAPI(title="Arbitralis Webhook PoC", version="0.1.0", lifespan=lifespan)

    @app.post("/webhook", status_code=status.HTTP_202_ACCEPTED, response_model=EnqueueResponse)
    async def receive_webhook(payload: WebhookPayload) -> EnqueueResponse:
        record = await app.state.processor.enqueue(
            user_id=payload.user_id,
            message=payload.message,
        )
        return EnqueueResponse(message_id=record.message_id, status=record.status)

    @app.get("/messages/{message_id}", response_model=MessageStatusResponse)
    async def get_message_status(message_id: str) -> MessageStatusResponse:
        record = app.state.store.get_message(message_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="message_not_found")

        return MessageStatusResponse(
            message_id=record.message_id,
            status=record.status,
            created_at=record.created_at,
            updated_at=record.updated_at,
            error=record.error,
        )

    @app.get("/outbound-mock")
    async def outbound_mock_log() -> list[dict[str, str]]:
        return [
            {
                "message_id": item.message_id,
                "user_id": item.user_id,
                "sent_at": item.sent_at.isoformat(),
            }
            for item in app.state.store.outbound_log
        ]

    return app


app = create_app()
