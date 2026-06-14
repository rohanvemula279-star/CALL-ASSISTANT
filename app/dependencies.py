from typing import Optional

from app.config import Settings, get_settings
from app.services.edgetts_service import EdgeTTSService
from app.services.edgetts_service import EdgeTTSService
from app.services.livekit_service import LiveKitService
from app.services.missed_call_service import MissedCallService
from app.services.ollama_client import OllamaClient
from app.services.piper_service import PiperService
from app.services.telegram_notifier import TelegramNotifier
from app.services.whisper_service import WhisperService
from app.storage.store import ConversationStore


class _Container:
    def __init__(self) -> None:
        self.settings: Settings = get_settings()
        self.ollama: OllamaClient = OllamaClient(self.settings)
        self.whisper: WhisperService = WhisperService(self.settings)
        self.piper: PiperService = PiperService(self.settings)
        self.telegram: TelegramNotifier = TelegramNotifier(self.settings)
        self.livekit: LiveKitService = LiveKitService(self.settings)
        self.edgetts: EdgeTTSService = EdgeTTSService()
        self.store: ConversationStore = ConversationStore(self.settings)
        self.missed_calls: MissedCallService = MissedCallService(
            settings=self.settings,
            store=self.store,
            ollama=self.ollama,
            piper=self.piper,
            telegram=self.telegram,
        )


_container: Optional[_Container] = None


def get_container() -> _Container:
    global _container
    if _container is None:
        _container = _Container()
    return _container


def get_settings_dep() -> Settings:
    return get_container().settings


def get_ollama() -> OllamaClient:
    return get_container().ollama


def get_whisper() -> WhisperService:
    return get_container().whisper


def get_piper() -> PiperService:
    return get_container().piper


def get_telegram() -> TelegramNotifier:
    return get_container().telegram


def get_store() -> ConversationStore:
    return get_container().store


def get_missed_call_service() -> MissedCallService:
    return get_container().missed_calls


def get_livekit() -> LiveKitService:
    return get_container().livekit


def get_edgetts() -> EdgeTTSService:
    return get_container().edgetts
