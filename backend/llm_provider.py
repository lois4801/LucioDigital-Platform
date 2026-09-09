"""Single seam for every LLM / image / speech call.

Two modes, chosen from the environment:
  - "emergent": EMERGENT_LLM_KEY is set -> routed through emergentintegrations.
  - "byo":      bring-your-own provider keys (OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY) -> litellm + openai SDK.
Call sites only import from this module, so a client can self-host with their own keys.
"""
import base64
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger("agency.llm_provider")


@dataclass
class UserMessage:
    text: str


@dataclass
class TextDelta:
    content: str


@dataclass
class StreamDone:
    pass


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def llm_mode() -> str:
    if _env("EMERGENT_LLM_KEY"):
        return "emergent"
    if _env("OPENAI_API_KEY") or _env("ANTHROPIC_API_KEY") or _env("GEMINI_API_KEY"):
        return "byo"
    return "none"


def llm_available() -> bool:
    return llm_mode() != "none"


def image_available() -> bool:
    return llm_mode() == "emergent" or bool(_env("OPENAI_API_KEY"))


def video_available() -> bool:
    """Video runs on the Fal proxy, which only exists in emergent mode unless FAL_KEY is supplied."""
    return llm_mode() == "emergent" or bool(_env("FAL_KEY"))


# ---------- BYO provider mapping ----------
_BYO_FALLBACK = {"openai": "gpt-4o-mini", "anthropic": "claude-3-5-sonnet-latest", "gemini": "gemini-1.5-pro"}
_BYO_KEY_ENV = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}


def _byo_target(provider: str, model: str):
    """Map the platform's model catalogue onto whichever provider key the operator supplied."""
    override = _env("LLM_MODEL_OVERRIDE")
    if override:
        return override
    if not _env(_BYO_KEY_ENV.get(provider, "")):
        for p, env_name in _BYO_KEY_ENV.items():
            if _env(env_name):
                logger.warning("No %s key configured; substituting %s/%s for requested %s/%s. "
                               "Set LLM_MODEL_OVERRIDE to pin a model.", provider, p, _BYO_FALLBACK[p], provider, model)
                provider, model = p, _BYO_FALLBACK[p]
                break
    prefix = {"openai": "", "anthropic": "anthropic/", "gemini": "gemini/"}[provider]
    return f"{prefix}{model}"


class _ByoChat:
    def __init__(self, provider, model, system, session_id):
        self.target = _byo_target(provider, model)
        self.system = system
        self.session_id = session_id

    def _messages(self, msg: UserMessage):
        out = []
        if self.system:
            out.append({"role": "system", "content": self.system})
        out.append({"role": "user", "content": msg.text})
        return out

    async def send_message(self, msg: UserMessage) -> str:
        import litellm
        res = await litellm.acompletion(model=self.target, messages=self._messages(msg))
        return res["choices"][0]["message"]["content"] or ""

    async def stream_message(self, msg: UserMessage):
        import litellm
        stream = await litellm.acompletion(model=self.target, messages=self._messages(msg), stream=True)
        async for chunk in stream:
            piece = (chunk["choices"][0].get("delta") or {}).get("content")
            if piece:
                yield TextDelta(piece)
        yield StreamDone()


class _EmergentChat:
    def __init__(self, provider, model, system, session_id):
        from emergentintegrations.llm.chat import LlmChat
        self._chat = LlmChat(api_key=_env("EMERGENT_LLM_KEY"), session_id=session_id,
                             system_message=system).with_model(provider, model)

    async def send_message(self, msg: UserMessage) -> str:
        from emergentintegrations.llm.chat import UserMessage as EUM
        reply = await self._chat.send_message(EUM(text=msg.text))
        return reply if isinstance(reply, str) else str(reply)

    async def stream_message(self, msg: UserMessage):
        from emergentintegrations.llm.chat import UserMessage as EUM, TextDelta as ETD, StreamDone as ESD
        async for ev in self._chat.stream_message(EUM(text=msg.text)):
            if isinstance(ev, ETD):
                yield TextDelta(ev.content)
            elif isinstance(ev, ESD):
                yield StreamDone()
                return
        yield StreamDone()


def get_chat(provider: str, model: str, system: str = "", session_id: str = "default"):
    mode = llm_mode()
    if mode == "none":
        raise RuntimeError("No LLM key configured. Set EMERGENT_LLM_KEY or a provider key (see backend/.env.example).")
    if mode == "emergent":
        return _EmergentChat(provider, model, system, session_id)
    return _ByoChat(provider, model, system, session_id)


async def generate_image(prompt: str, number_of_images: int = 1) -> List[bytes]:
    if llm_mode() == "emergent":
        from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
        return await OpenAIImageGeneration(api_key=_env("EMERGENT_LLM_KEY")).generate_images(
            prompt=prompt, model="gpt-image-1", number_of_images=number_of_images)
    key = _env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Image generation needs OPENAI_API_KEY (or EMERGENT_LLM_KEY).")
    from openai import AsyncOpenAI
    res = await AsyncOpenAI(api_key=key).images.generate(
        model=_env("IMAGE_MODEL") or "gpt-image-1", prompt=prompt, n=number_of_images)
    return [base64.b64decode(d.b64_json) for d in res.data if d.b64_json]


async def generate_speech(text: str, voice: str = "alloy", model: str = "tts-1") -> bytes:
    if llm_mode() == "emergent":
        from emergentintegrations.llm.openai import OpenAITextToSpeech
        return await OpenAITextToSpeech(api_key=_env("EMERGENT_LLM_KEY")).generate_speech(text=text, model=model, voice=voice)
    key = _env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Text-to-speech needs OPENAI_API_KEY, ELEVENLABS_API_KEY or EMERGENT_LLM_KEY.")
    from openai import AsyncOpenAI
    res = await AsyncOpenAI(api_key=key).audio.speech.create(model=model, voice=voice, input=text)
    return res.content


def status() -> dict:
    return {"mode": llm_mode(), "text": llm_available(), "images": image_available(), "video": video_available()}
