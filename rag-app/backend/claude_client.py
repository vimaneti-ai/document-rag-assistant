import os
from dataclasses import asdict, dataclass
from typing import List, Optional

import anthropic
from dotenv import load_dotenv


load_dotenv()

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1200
MAX_CACHED_CONTEXT_CHARS = int(os.getenv("MAX_CACHED_CONTEXT_CHARS", "120000"))


@dataclass
class UsageStats:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    cache_hit: bool

    def to_dict(self) -> dict:
        return asdict(self)


class ClaudeClient:
    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=api_key)

    def ask(
        self,
        question: str,
        document_context: str,
        document_name: str,
        retrieved_context: str,
        conversation_history: Optional[List[dict]] = None,
    ) -> tuple[str, UsageStats]:
        if self.client is None:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in backend/.env")

        messages = self._build_messages(question, retrieved_context, conversation_history or [])
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": self._system_prompt(document_name, document_context),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
        )

        answer = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = self._usage_stats(response.usage)
        return answer, usage

    def summarize_document(self, document_context: str, document_name: str) -> str:
        if self.client is None:
            return "Document processed and indexed. Add ANTHROPIC_API_KEY to backend/.env to enable Claude summaries and chat."

        excerpt = document_context[:12000]
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=320,
            system="You write concise executive summaries for uploaded documents.",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Summarize the key topics in this document in 3-4 sentences.\n\n"
                        f"Document name: {document_name}\n\n{excerpt}"
                    ),
                }
            ],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )

    def _system_prompt(self, document_name: str, document_context: str) -> str:
        context = document_context
        if len(context) > MAX_CACHED_CONTEXT_CHARS:
            context = (
                context[:MAX_CACHED_CONTEXT_CHARS]
                + "\n\n[Document context truncated for model safety. Use retrieved excerpts for precise details.]"
            )
        return f"""You are Adaptive RAG, a precise document assistant.

Use the document context below as the trusted source of truth.

Rules:
- Answer only from the document content and retrieved excerpts.
- If the document does not contain the answer, say that the information is not in the uploaded document.
- Be concise, useful, and professional.
- When relevant, mention the source chunk or page in natural language.
- Do not fabricate citations, facts, numbers, or conclusions.

Document name: {document_name}

Document context:
{context}"""

    def _build_messages(
        self,
        question: str,
        retrieved_context: str,
        conversation_history: List[dict],
    ) -> List[dict]:
        messages = []
        for item in conversation_history[-12:]:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Use these top retrieved excerpts first, then the cached document context if needed.\n\n"
                    f"{retrieved_context}\n\nQuestion: {question}"
                ),
            }
        )
        return messages

    def _usage_stats(self, usage) -> UsageStats:
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        cache_read_tokens = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cache_write_tokens = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        cost = (
            (input_tokens / 1_000_000) * 1.00
            + (output_tokens / 1_000_000) * 5.00
            + (cache_read_tokens / 1_000_000) * 0.10
            + (cache_write_tokens / 1_000_000) * 1.25
        )
        return UsageStats(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            cost_usd=round(cost, 6),
            cache_hit=cache_read_tokens > 0,
        )
