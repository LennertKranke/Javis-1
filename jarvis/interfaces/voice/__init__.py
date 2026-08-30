"""Sprache: eine zusaetzliche Bedienweise, kein Ersatz fuer die bestehenden.

Sie liest vor und kann anhalten. Senden, freigeben und fortsetzen gehen
weiterhin nur ueber Dashboard und Kommandozeile -- ein Mikrofon hoert den
ganzen Raum, und was jeder ausloesen kann, darf nicht nach aussen wirken.
"""

from jarvis.interfaces.voice.intents import (
    ABSICHTEN,
    ANHALTEN,
    BRIEFING,
    HANDELN,
    LESEND,
    OFFEN,
    STATUS,
    UNBEKANNT,
    Erkennung,
    erkenne_mit_regeln,
    loese_weckwort,
)
from jarvis.interfaces.voice.session import Antwort, VoiceSession, build_session
from jarvis.interfaces.voice.speak import MacSpeaker, Speaker, SpeechError, TextSpeaker
from jarvis.interfaces.voice.transcribe import (
    CommandRecorder,
    RecordingError,
    StaticTranscriber,
    Transcriber,
    TranscriptionError,
    WhisperCppTranscriber,
)

__all__ = [
    "ABSICHTEN",
    "ANHALTEN",
    "BRIEFING",
    "HANDELN",
    "LESEND",
    "OFFEN",
    "STATUS",
    "UNBEKANNT",
    "Antwort",
    "CommandRecorder",
    "Erkennung",
    "MacSpeaker",
    "RecordingError",
    "Speaker",
    "SpeechError",
    "StaticTranscriber",
    "TextSpeaker",
    "Transcriber",
    "TranscriptionError",
    "VoiceSession",
    "WhisperCppTranscriber",
    "build_session",
    "erkenne_mit_regeln",
    "loese_weckwort",
]
