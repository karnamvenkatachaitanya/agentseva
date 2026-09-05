"""Small Hugging Face Router adapter with an Anthropic-like response surface.

The commerce state machine stays provider-agnostic while this adapter translates
its structured messages and tools to the OpenAI-compatible Hugging Face API.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List

import httpx


class _Messages:
    def __init__(self, api_key: str, base_url: str, timeout: float):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def _tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for tool in tools
        ]

    @staticmethod
    def _messages(system: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        for message in messages:
            role = message["role"]
            content = message.get("content", "")
            if isinstance(content, str):
                output.append({"role": role, "content": content})
                continue

            if role == "assistant":
                text = "\n".join(
                    block.get("text", "") for block in content if block.get("type") == "text"
                ).strip()
                tool_calls = [
                    {
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block.get("input", {})),
                        },
                    }
                    for block in content
                    if block.get("type") == "tool_use"
                ]
                item: Dict[str, Any] = {"role": "assistant", "content": text or None}
                if tool_calls:
                    item["tool_calls"] = tool_calls
                output.append(item)
                continue

            for block in content:
                if block.get("type") == "tool_result":
                    output.append(
                        {
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block.get("content", ""),
                        }
                    )
        return output

    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        temperature: float,
        system: str,
        tools: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
    ) -> Any:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": model,
                "messages": self._messages(system, messages),
                "tools": self._tools(tools),
                "tool_choice": "auto",
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]
        content: List[Any] = []
        if message.get("content"):
            content.append(SimpleNamespace(type="text", text=message["content"]))
        for call in message.get("tool_calls") or []:
            function = call["function"]
            raw_arguments = function.get("arguments") or "{}"
            arguments = raw_arguments if isinstance(raw_arguments, dict) else json.loads(raw_arguments)
            content.append(
                SimpleNamespace(
                    type="tool_use",
                    id=call["id"],
                    name=function["name"],
                    input=arguments,
                )
            )
        return SimpleNamespace(content=content, stop_reason=payload["choices"][0].get("finish_reason"))


class HuggingFaceToolClient:
    """Adapter consumed by :class:`CommerceAgentCore`."""

    def __init__(self, api_key: str, base_url: str, timeout: float = 60.0):
        self.messages = _Messages(api_key=api_key, base_url=base_url, timeout=timeout)