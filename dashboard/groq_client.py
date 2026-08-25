import json
import os
import urllib.request
import urllib.error


class GroqError(Exception):
    pass


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

    model = model or os.environ.get("GROQ_MODEL", "groq/compound-mini")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }

    if tools:
        payload["tools"] = tools
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
        try:
            details = e.read().decode("utf-8")
        except Exception:
            details = str(e)
        raise GroqError(f"Groq HTTPError: {e.code} {details}")
    except Exception as e:
        raise GroqError(f"Groq request failed: {e}")

    data = json.loads(body)

    # Tool call response döndür (ham)
    if tools:
        return data

    # Normal metin yanıtı
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise GroqError(f"Unexpected Groq response: {data}")
