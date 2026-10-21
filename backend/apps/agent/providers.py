"""LLM provider abstraction. Business tools never talk to a vendor SDK directly."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger("paypilot.agent")


class ProviderError(Exception):
    code = "provider_error"
    public_message = "The AI provider could not complete that request."


class ProviderNotConfigured(ProviderError):
    code = "not_configured"
    public_message = "No AI provider is configured on the server."


class ProviderTimeout(ProviderError):
    code = "provider_timeout"
    public_message = "The AI provider timed out."


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class ModelTurn:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider:
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelTurn:
        raise NotImplementedError


class OpenAICompatibleProvider(LLMProvider):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelTurn:
        if not settings.LLM_API_KEY or not settings.LLM_MODEL:
            raise ProviderNotConfigured()
        url = settings.LLM_BASE_URL.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": settings.LLM_MODEL,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"},
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        except requests.Timeout as exc:
            raise ProviderTimeout() from exc
        except requests.RequestException as exc:
            logger.warning("llm_transport_error")
            raise ProviderError() from exc
        if response.status_code >= 400:
            logger.warning("llm_http_error", extra={"http_status": response.status_code})
            raise ProviderError()
        choice = (response.json().get("choices") or [{}])[0]
        message = choice.get("message") or {}
        calls = []
        for raw in message.get("tool_calls") or []:
            fn = raw.get("function") or {}
            calls.append(
                ToolCall(
                    id=str(raw.get("id") or ""),
                    name=str(fn.get("name") or ""),
                    arguments=str(fn.get("arguments") or "{}"),
                )
            )
        return ModelTurn(content=str(message.get("content") or ""), tool_calls=calls)


def get_provider() -> LLMProvider:
    return OpenAICompatibleProvider()
