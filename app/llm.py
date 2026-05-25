import asyncio
import random
from typing import Protocol


class LLMClient(Protocol):
    async def generate_reply(self, user_message: str) -> str:
        ...


class SimulatedLLMClient:
    def __init__(self, fail_rate: float = 0.2) -> None:
        self.fail_rate = fail_rate

    async def generate_reply(self, user_message: str) -> str:
        chance = random.random()

        if chance < 0.2:
            await asyncio.sleep(0.05)
        elif chance < 0.8:
            await asyncio.sleep(0.8)
        else:
            await asyncio.sleep(2.5)

        if random.random() < self.fail_rate:
            raise RuntimeError("simulated_llm_failure")

        return f"Recebemos sua mensagem e vamos seguir com a negociacao: {user_message[:80]}"
