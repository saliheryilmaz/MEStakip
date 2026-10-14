import json
import os
import urllib.request
import urllib.error
import socket
import ssl


class GroqError(Exception):
    def __init__(self, message, status_code=None, error_code=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


def groq_chat_completion(*, messages, model=None, api_key=None,
                         temperature=0.2, max_tokens=1000, timeout_s=45,
                         tools=None, tool_choice=None):
    """
    Groq Chat Completions client (OpenAI-compatible endpoint).
    Tool calling desteği eklenmiştir.
    """
    api_key = api_key if api_key is not None else os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise GroqError("GROQ_API_KEY is not set")

    model = model or os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }

    if tools:
        payload["tools"] = tools
        payload["parallel_tool_calls"] = False
    if tool_choice:
        payload["tool_choice"] = tool_choice

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MEStakip/2.0 (+https://localhost)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        error_code = None
        try:
            error = json.loads(e.read(65536)).get("error", {})
            code = error.get("code") if isinstance(error, dict) else None
            if code in {"model_not_found", "model_decommissioned", "tool_use_failed"}:
                error_code = code
        except (ValueError, AttributeError):
            pass
        raise GroqError(f"Groq HTTPError: {e.code}", status_code=e.code, error_code=error_code) from e
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        code = "connection_error"
        if isinstance(reason, (socket.timeout, TimeoutError)):
            code = "timeout"
        elif isinstance(reason, ssl.SSLError):
            code = "tls_error"
        elif getattr(reason, "winerror", None) == 10013 or getattr(reason, "errno", None) in {13, 10013}:
            code = "network_blocked"
        raise GroqError("Groq connection failed", error_code=code) from e

    try:
        data = json.loads(body)
        if not isinstance(data, dict) or not data.get("choices"):
            raise ValueError("Missing choices")
    except ValueError as e:
        raise GroqError("Unexpected Groq response", error_code="invalid_response") from e

    # Tool call response döndür (ham)
    if tools:
        return data

    # Normal metin yanıtı
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise GroqError("Unexpected Groq response", error_code="invalid_response")
