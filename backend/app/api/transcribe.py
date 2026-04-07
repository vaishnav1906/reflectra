import logging
import os
import tempfile
from pathlib import Path

import ffmpeg
import whisper
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["speech"])

MAX_AUDIO_BYTES = 8 * 1024 * 1024  # 8 MB
ALLOWED_CONTENT_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/flac",
    "application/octet-stream",  # fallback used by some browsers
}

WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")

try:
    # Load once at startup/import time to avoid per-request cold starts.
    whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
    logger.info("Whisper model loaded: %s", WHISPER_MODEL_NAME)
except Exception:
    whisper_model = None
    logger.exception("Failed to load Whisper model '%s'", WHISPER_MODEL_NAME)


def _convert_to_wav(input_path: str, output_path: str) -> None:
    ffmpeg.input(input_path).output(
        output_path,
        format="wav",
        acodec="pcm_s16le",
        ac=1,
        ar="16000",
    ).overwrite_output().run(capture_stdout=True, capture_stderr=True)


def _transcribe_audio(wav_path: str) -> dict:
    if whisper_model is None:
        raise RuntimeError("Whisper model is not available")

    return whisper_model.transcribe(wav_path, fp16=False)


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES and not content_type.startswith("audio/"):
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {content_type}")

    suffix = Path(file.filename).suffix or ".bin"
    temp_input_path = ""
    temp_wav_path = ""
    total_bytes = 0

    try:
        with tempfile.NamedTemporaryFile(delete=False, prefix="reflectra_audio_", suffix=suffix) as tmp_input:
            temp_input_path = tmp_input.name

            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break

                total_bytes += len(chunk)
                if total_bytes > MAX_AUDIO_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Audio file too large. Keep recordings under 15 seconds.",
                    )

                tmp_input.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")

        with tempfile.NamedTemporaryFile(delete=False, prefix="reflectra_audio_", suffix=".wav") as tmp_wav:
            temp_wav_path = tmp_wav.name

        await run_in_threadpool(_convert_to_wav, temp_input_path, temp_wav_path)
        result = await run_in_threadpool(_transcribe_audio, temp_wav_path)

        text = (result.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="No speech detected. Please try again.")

        return {"text": text}
    except HTTPException:
        raise
    except ffmpeg.Error as exc:
        stderr_output = (exc.stderr or b"").decode("utf-8", errors="ignore")
        logger.warning("Audio conversion failed: %s", stderr_output)
        raise HTTPException(status_code=400, detail="Corrupt or unsupported audio format")
    except RuntimeError as exc:
        logger.error("Transcription unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Transcription model is not available")
    except Exception as exc:
        logger.exception("Unexpected transcription error")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(exc)}")
    finally:
        await file.close()

        for path in (temp_input_path, temp_wav_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    logger.warning("Failed to remove temp file: %s", path)
