import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .llm import LLMClient, SimulatedLLMClient
from .schemas import MessageRecord, OutboundMessage, ProcessingStatus, WebhookEvent, utcnow

logger = logging.getLogger("arbitralis.poc")


def _mask_user_id(user_id: str) -> str:
    if len(user_id) <= 4:
        return "*" * len(user_id)
    return f"{'*' * (len(user_id) - 4)}{user_id[-4:]}"


@dataclass
class InMemoryStore:
    messages: Dict[str, MessageRecord] = field(default_factory=dict)
    outbound_log: List[OutboundMessage] = field(default_factory=list)

    def create_message(self, user_id: str, message: str) -> MessageRecord:
        now = utcnow()
        message_id = str(uuid.uuid4())
        record = MessageRecord(
            message_id=message_id,
            user_id=user_id,
            message=message,
            status=ProcessingStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
        self.messages[message_id] = record
        return record

    def get_message(self, message_id: str) -> Optional[MessageRecord]:
        return self.messages.get(message_id)


class OutboundGateway:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def send_message(self, message_id: str, user_id: str, reply: str) -> None:
        now = utcnow()
        self.store.outbound_log.append(
            OutboundMessage(
                message_id=message_id,
                user_id=user_id,
                reply=reply,
                sent_at=now,
            )
        )
        logger.info(
            "outbound_message_dispatched",
            extra={
                "message_id": message_id,
                "user_id_masked": _mask_user_id(user_id),
                "reply_size": len(reply),
            },
        )


class MessageProcessor:
    def __init__(
        self,
        store: InMemoryStore,
        llm_client: Optional[LLMClient] = None,
        outbound_gateway: Optional[OutboundGateway] = None,
    ) -> None:
        self.store = store
        self.queue: asyncio.Queue[WebhookEvent] = asyncio.Queue()
        self.llm_client = llm_client or SimulatedLLMClient()
        self.outbound_gateway = outbound_gateway or OutboundGateway(store)
        self._worker_task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task is None:
            return

        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass
        finally:
            self._worker_task = None

    async def enqueue(self, user_id: str, message: str) -> MessageRecord:
        record = self.store.create_message(user_id=user_id, message=message)
        event = WebhookEvent(
            message_id=record.message_id,
            user_id=user_id,
            message=message,
            received_at=record.created_at,
        )
        await self.queue.put(event)

        logger.info(
            "webhook_event_enqueued",
            extra={
                "message_id": record.message_id,
                "user_id_masked": _mask_user_id(user_id),
                "message_size": len(message),
            },
        )

        return record

    async def _worker_loop(self) -> None:
        while True:
            event = await self.queue.get()
            try:
                await self._process(event)
            finally:
                self.queue.task_done()

    async def _process(self, event: WebhookEvent) -> None:
        record = self.store.get_message(event.message_id)
        if record is None:
            return

        record.status = ProcessingStatus.PROCESSING
        record.updated_at = utcnow()

        try:
            reply = await self.llm_client.generate_reply(event.message)
            await self.outbound_gateway.send_message(
                message_id=event.message_id,
                user_id=event.user_id,
                reply=reply,
            )
            record.status = ProcessingStatus.SENT
            record.error = None
        except Exception as exc:
            record.status = ProcessingStatus.FAILED
            record.error = str(exc)
            logger.warning(
                "llm_processing_failed",
                extra={
                    "message_id": event.message_id,
                    "user_id_masked": _mask_user_id(event.user_id),
                    "error": str(exc),
                },
            )
        finally:
            record.updated_at = utcnow()
