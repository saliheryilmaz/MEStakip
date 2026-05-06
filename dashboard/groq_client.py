import json
import os
import urllib.request
import urllib.error


class GroqError(Exception):
    pass


def groq_chat_completion(*, messages, model=None, api_key=None, temperature=0.2, max_tokens=500, timeout_s=30):
    """
    Minimal Groq Chat Completions client (OpenAI-compatible endpoint).
    """
    api_key = api_key if api_key is not None else os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise GroqError("GROQ_API_KEY is not set")

    model = model or os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Some networks/CDNs block requests without a UA.
            "User-Agent": "MEStakip/1.0 (+https://localhost)",
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
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise GroqError(f"Unexpected Groq response: {data}")

