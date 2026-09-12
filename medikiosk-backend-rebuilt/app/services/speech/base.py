"""
Speech seam.

The default path is the browser: Web Speech API for recognition and
SpeechSynthesis for playback, which costs nothing and works offline on the
kiosk. The server-side adapter exists for Hindi and Kannada, where browser
accuracy is the weak point, and slots in behind the same interface.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    language: str
    confidence: float | None
    provider: str


class SpeechService(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    async def transcribe(self, audio: bytes, mime_type: str, language: str) -> TranscriptionResult: ...


class TTSService(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    async def synthesize(self, text: str, language: str) -> bytes | None:
        """None tells the client to fall back to browser SpeechSynthesis."""


class BrowserPassthroughSpeech(SpeechService):
    """
    The browser already did the work. This records the result through the same
    interface so callers never branch on which path produced the text.
    """

    name = "browser"

    async def transcribe(self, audio: bytes, mime_type: str, language: str) -> TranscriptionResult:
        raise NotImplementedError(
            "Browser speech recognition runs client-side. Post the transcript to "
            "the conversation answer endpoint with via_voice=true instead."
        )


class BrowserPassthroughTTS(TTSService):
    name = "browser"

    async def synthesize(self, text: str, language: str) -> bytes | None:
        return None
