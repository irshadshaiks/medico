from __future__ import annotations

from functools import lru_cache

from app.services.speech.base import BrowserPassthroughSpeech, BrowserPassthroughTTS, SpeechService, TTSService


@lru_cache
def get_speech_service() -> SpeechService:
    return BrowserPassthroughSpeech()


@lru_cache
def get_tts_service() -> TTSService:
    return BrowserPassthroughTTS()
