from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import DbDep, UserDep
from app.assistant.llm import Extractor, get_extractor
from app.assistant.schemas import StartVoiceSession, TranscriptionOut, VoiceReply, VoiceTurn
from app.assistant.service import VoiceAssistant
from app.assistant.transcribe import Transcriber, get_transcriber
from app.config import get_settings
from app.errors import AppError

router = APIRouter(prefix="/voice", tags=["voice"])

ExtractorDep = Annotated[Extractor, Depends(get_extractor)]


@router.post("/transcribe", response_model=TranscriptionOut)
async def transcribe(
    _: UserDep,
    transcriber: Annotated[Transcriber, Depends(get_transcriber)],
    audio: Annotated[UploadFile, File(description="m4a, mp3, wav, webm, ogg or flac")],
    language: Annotated[str | None, Form(pattern=r"^[a-z]{2}$")] = None,
) -> TranscriptionOut:
    """Server-side speech recognition (Groq Whisper). Use when the phone can't transcribe,
    e.g. for pending voice notes recorded offline. `language` is ISO-639-1 ("ro", "en")."""
    limit = get_settings().voice_max_audio_bytes
    data = await audio.read(limit + 1)
    if not data:
        raise AppError(400, "empty_audio", "The audio file is empty")
    if len(data) > limit:
        raise AppError(413, "audio_too_large", f"Audio must be at most {limit} bytes")
    text = await transcriber(
        data, audio.filename or "audio.m4a", audio.content_type or "audio/m4a", language
    )
    return TranscriptionOut(text=text.strip())


@router.post("/sessions", response_model=VoiceTurn)
async def start_session(
    body: StartVoiceSession, user: UserDep, session: DbDep, extractor: ExtractorDep
) -> VoiceTurn:
    """Start a voice entry from a transcript. The app speaks `speak`, plays `haptic`, and if
    `status` is question/confirm/not_understood listens and calls `/reply`."""
    turn = await VoiceAssistant(session, user, extractor).start(body)
    await session.commit()
    return turn


@router.post("/sessions/{thread_id}/reply", response_model=VoiceTurn)
async def reply(
    thread_id: UUID, body: VoiceReply, user: UserDep, session: DbDep, extractor: ExtractorDep
) -> VoiceTurn:
    turn = await VoiceAssistant(session, user, extractor).reply(thread_id, body.text)
    await session.commit()
    return turn


@router.get("/sessions/{thread_id}", response_model=VoiceTurn)
async def current(
    thread_id: UUID, user: UserDep, session: DbDep, extractor: ExtractorDep
) -> VoiceTurn:
    """Repeat the pending question (e.g. after the app was closed mid-conversation)."""
    return await VoiceAssistant(session, user, extractor).current(thread_id)


@router.post("/notes/{voice_note_id}/process", response_model=VoiceTurn)
async def process_note(
    voice_note_id: UUID, user: UserDep, session: DbDep, extractor: ExtractorDep
) -> VoiceTurn:
    """Start (or resume) the conversation for a voice note recorded offline. Never auto-saves:
    the user still confirms."""
    turn = await VoiceAssistant(session, user, extractor).process_voice_note(voice_note_id)
    await session.commit()
    return turn
