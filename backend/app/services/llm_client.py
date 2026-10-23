"""LLM + embedding client.

Wraps the OpenAI SDK behind a small interface so the provider can be swapped.
When no API key is configured (or LLM_PROVIDER=mock) a deterministic offline
mock is used, which lets you develop, run tests and demo without any cost.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.core.config import settings

log = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[\w஀-௿ऀ-ॿ]+", re.UNICODE)
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "for", "to", "in", "on", "and", "or", "what",
    "how", "when", "where", "which", "who", "do", "does", "i", "my", "me", "can", "you", "your", "it",
    "this", "that", "be", "with", "at", "by", "from", "as", "will", "there", "please", "tell", "about",
}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


@dataclass
class StreamResult:
    """Collects usage while a stream is consumed."""
    usage: Usage = field(default_factory=Usage)


class BaseLLM:
    name = "base"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    async def complete(self, messages: list[dict], max_tokens: int = 200, model: str | None = None) -> tuple[str, Usage]:
        raise NotImplementedError

    async def stream(self, messages: list[dict], result: StreamResult, model: str | None = None) -> AsyncIterator[str]:
        raise NotImplementedError
        yield  # pragma: no cover


class OpenAILLM(BaseLLM):
    name = "openai"

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL, timeout=60, max_retries=2)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 96):  # batch to stay under request limits
            batch = [t.replace("\n", " ")[:8000] for t in texts[i:i + 96]]
            resp = await self.client.embeddings.create(model=settings.EMBEDDING_MODEL, input=batch,
                                                       dimensions=settings.EMBEDDING_DIM)
            out.extend(d.embedding for d in resp.data)
        return out

    async def complete(self, messages, max_tokens=200, model=None):
        model = model or settings.CHAT_MODEL
        resp = await self.client.chat.completions.create(
            model=model, messages=messages, temperature=0, max_tokens=max_tokens,
        )
        u = resp.usage
        return (resp.choices[0].message.content or "").strip(), Usage(u.prompt_tokens if u else 0, u.completion_tokens if u else 0, model)

    async def stream(self, messages, result, model=None):
        model = model or settings.CHAT_MODEL
        result.usage.model = model
        stream = await self.client.chat.completions.create(
            model=model, messages=messages, temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS, stream=True, stream_options={"include_usage": True},
        )
        async for chunk in stream:
            if chunk.usage:
                result.usage.prompt_tokens = chunk.usage.prompt_tokens
                result.usage.completion_tokens = chunk.usage.completion_tokens
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class MockLLM(BaseLLM):
    """Offline stand-in. Embeddings = hashed bag-of-words (so similar texts really
    are similar). Answers = the most relevant sentences from the supplied context."""

    name = "mock"

    def _vec(self, text: str) -> list[float]:
        dim = settings.EMBEDDING_DIM
        v = [0.0] * dim
        for tok in tokenize(text):
            if tok in STOPWORDS:
                continue
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % dim] += 1.0 if (h >> 8) % 2 else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    async def embed(self, texts):
        return [self._vec(t) for t in texts]

    async def complete(self, messages, max_tokens=200, model=None):
        last = messages[-1]["content"]
        if "STANDALONE" in messages[0]["content"]:
            # Query rewrite: only merge with the previous turn for obvious follow-ups.
            m = re.search(r"Follow-up:\s*(.*)", last, re.S)
            hist = re.findall(r"User:\s*(.*)", last)
            follow = m.group(1).strip() if m else last
            prev = hist[-1].strip() if hist else ""
            if re.match(r"^(and|also|what about|how about|for|then)\b", follow.lower()):
                return f"{prev} {follow}".strip(), Usage(model="mock")
            return follow, Usage(model="mock")
        return last[:max_tokens], Usage(model="mock")

    async def stream(self, messages, result, model=None):
        result.usage.model = "mock"
        text = self._extractive_answer(messages[-1]["content"])
        for word in re.split(r"(\s+)", text):
            if word:
                yield word

    @staticmethod
    def _extractive_answer(prompt: str) -> str:
        q_match = re.search(r"QUESTION:\s*(.*)$", prompt, re.S)
        question = q_match.group(1).strip() if q_match else prompt
        def stems(text: str) -> set[str]:
            return {t[:-1] if len(t) > 3 and t.endswith("s") else t for t in tokenize(text) if t not in STOPWORDS}

        q_tokens = stems(question)
        wants_number = bool(re.search(r"\b(fee|fees|cost|date|when|last|how much|evlo|package|seats?)\b", question.lower()))
        blocks = re.findall(r"\[(\d+)\][^\n]*\n(.*?)(?=\n\[\d+\]|\nQUESTION:|\Z)", prompt, re.S)
        best: list[tuple[float, str, str]] = []
        for idx, body in blocks:
            for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z])|\n+", body):
                sent = sent.strip()
                if len(sent) < 12 or set(sent) <= set("|-: "):
                    continue
                overlap = len(q_tokens & stems(sent))
                if not overlap:
                    continue
                score = float(overlap)
                has_digit = bool(re.search(r"\d", sent))
                if wants_number and has_digit:
                    score += 0.75
                if sent.startswith("#") or (sent.startswith("|") and not has_digit):
                    score -= 1.0  # headings / table headers rarely answer the question
                best.append((score, idx, sent.lstrip("#-* ").replace("|", " ").strip()))
        best = [b for b in best if b[0] >= 1.0]
        if not best:
            return "NO_ANSWER"
        best.sort(key=lambda x: -x[0])
        top = best[0][0]
        picked = [b for b in best[:3] if b[0] >= top - 0.5]
        return "\n".join(f"- {re.sub(' +', ' ', s)} [{i}]" if len(picked) > 1 else f"{s} [{i}]" for _, i, s in picked)


_llm: BaseLLM | None = None


def get_llm() -> BaseLLM:
    global _llm
    if _llm is None:
        if settings.is_mock_llm:
            log.warning("Using MOCK LLM provider (no OPENAI_API_KEY set). Answers are extractive only.")
            _llm = MockLLM()
        else:
            _llm = OpenAILLM()
    return _llm


def set_llm(llm: BaseLLM | None) -> None:
    """Override the provider (used in tests)."""
    global _llm
    _llm = llm
