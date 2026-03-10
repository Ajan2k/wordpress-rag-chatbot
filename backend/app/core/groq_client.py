# backend/app/core/groq_client.py
"""
Singleton wrapper around the Groq Cloud API client.

Offloads the heavy generative workload (Llama 3.3 70B) to Groq's
ultra-low-latency inference infrastructure, keeping local VRAM free
for the embedding model.
"""
import logging
import threading
from typing import Generator

from groq import Groq
from app.core.settings import settings

logger = logging.getLogger(__name__)

# ── System prompt for the healthcare RAG assistant ──────────────────
SYSTEM_PROMPT = (
    "You are Herald Kitchen's expert healthcare assistant. "
    "You answer user questions ONLY based on the provided context "
    "retrieved from the WordPress Knowledge Base. "
    "If the context does not contain the answer, say so honestly. "
    "You must reply in the SAME language the user asks in. "
    "Keep answers concise, accurate, and helpful."
)


class GroqClient:
    """
    Thread-safe Singleton for Groq API interactions.
    Provides both blocking and streaming chat completions.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> "GroqClient":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialised = False
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        if self._initialised:
            return
        self._client = Groq(api_key=settings.groq_api_key.get_secret_value())
        self._model = settings.groq_model
        self._initialised = True
        logger.info("Groq client initialised (model=%s).", self._model)

    # ── Blocking completion ─────────────────────────────────────────

    def generate(self, context: str, question: str) -> str:
        """
        Send a single-turn RAG prompt and return the full response text.
        """
        messages = self._build_messages(context, question)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
        )
        return response.choices[0].message.content

    # ── Streaming completion (for SSE) ──────────────────────────────

    def generate_stream(self, context: str, question: str) -> Generator[str, None, None]:
        """
        Yield tokens one-by-one for Server-Sent Events streaming.
        """
        messages = self._build_messages(context, question)
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _build_messages(context: str, question: str) -> list:
        """
        Construct the messages payload with the RAG context
        injected into the user turn.
        """
        user_content = (
            f"### Context (from WordPress knowledge base):\n"
            f"{context}\n\n"
            f"### User question:\n"
            f"{question}"
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
