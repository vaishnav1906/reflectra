import { useEffect, useRef, useState } from "react";
import { Loader2, Mic, Send, Square } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
}

const API_BASE = "/api";
const MAX_RECORDING_MS = 15_000;
const MAX_AUDIO_BYTES = 8 * 1024 * 1024;
const SILENCE_THRESHOLD_RMS = 0.015;
const SILENCE_HOLD_MS = 2_000;
const MIN_RECORDING_MS_FOR_SILENCE_STOP = 1_200;
const SILENCE_CHECK_INTERVAL_MS = 200;

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingStartedAtRef = useRef<number>(0);
  const maxDurationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const silenceIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  const clearTimers = () => {
    if (maxDurationTimeoutRef.current) {
      clearTimeout(maxDurationTimeoutRef.current);
      maxDurationTimeoutRef.current = null;
    }

    if (silenceIntervalRef.current) {
      clearInterval(silenceIntervalRef.current);
      silenceIntervalRef.current = null;
    }

    silenceStartRef.current = null;
  };

  const cleanupMediaResources = () => {
    clearTimers();

    if (audioContextRef.current) {
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      cleanupMediaResources();
    };
  }, []);

  const submitMessage = (rawText: string) => {
    const trimmed = rawText.trim();
    if (!trimmed || isLoading || isTranscribing || isRecording) {
      return;
    }

    onSend(trimmed);
    setMessage("");
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submitMessage(message);
  };

  const stopRecording = () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state !== "recording") {
      return;
    }

    clearTimers();
    setIsRecording(false);

    recorder.stop();

    if (audioContextRef.current) {
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
  };

  const transcribeRecording = async (audioBlob: Blob) => {
    if (audioBlob.size === 0) {
      setSpeechError("No audio captured. Please try again.");
      return;
    }

    if (audioBlob.size > MAX_AUDIO_BYTES) {
      setSpeechError("Recording is too large. Keep voice notes under 15 seconds.");
      return;
    }

    setIsTranscribing(true);
    setSpeechError(null);

    try {
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.webm");

      const response = await fetch(`${API_BASE}/transcribe`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        const detail = typeof payload?.detail === "string" ? payload.detail : "Transcription failed";
        throw new Error(detail);
      }

      const transcript = typeof payload?.text === "string" ? payload.text.trim() : "";
      if (!transcript) {
        throw new Error("No speech detected. Please try again.");
      }

      const hasDraft = message.trim().length > 0;

      if (hasDraft) {
        setMessage((prev) => `${prev.trim()} ${transcript}`.trim());
      } else {
        onSend(transcript);
      }
    } catch (error) {
      const errMessage = error instanceof Error ? error.message : "Unable to transcribe audio";
      setSpeechError(errMessage);
    } finally {
      setIsTranscribing(false);
    }
  };

  const startSilenceDetection = (stream: MediaStream) => {
    if (typeof window === "undefined" || !("AudioContext" in window)) {
      return;
    }

    try {
      const audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser();
      const source = audioContext.createMediaStreamSource(stream);

      analyser.fftSize = 2048;
      source.connect(analyser);

      const data = new Uint8Array(analyser.fftSize);
      audioContextRef.current = audioContext;

      silenceIntervalRef.current = setInterval(() => {
        const recorder = mediaRecorderRef.current;
        if (!recorder || recorder.state !== "recording") {
          return;
        }

        analyser.getByteTimeDomainData(data);

        let sum = 0;
        for (let i = 0; i < data.length; i += 1) {
          const normalized = (data[i] - 128) / 128;
          sum += normalized * normalized;
        }

        const rms = Math.sqrt(sum / data.length);
        const now = Date.now();
        const elapsed = now - recordingStartedAtRef.current;

        if (rms < SILENCE_THRESHOLD_RMS) {
          if (silenceStartRef.current === null) {
            silenceStartRef.current = now;
          }

          const silentDuration = now - silenceStartRef.current;
          if (
            elapsed >= MIN_RECORDING_MS_FOR_SILENCE_STOP
            && silentDuration >= SILENCE_HOLD_MS
          ) {
            stopRecording();
          }
        } else {
          silenceStartRef.current = null;
        }
      }, SILENCE_CHECK_INTERVAL_MS);
    } catch {
      // Silence detection is best-effort; recording still works without it.
    }
  };

  const startRecording = async () => {
    if (isLoading || isTranscribing) {
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setSpeechError("Microphone recording is not supported in this browser.");
      return;
    }

    setSpeechError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const preferredTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const mimeType = preferredTypes.find((type) => MediaRecorder.isTypeSupported(type));

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      audioChunksRef.current = [];
      recordingStartedAtRef.current = Date.now();

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setSpeechError("Microphone recording failed. Please retry.");
        setIsRecording(false);
        cleanupMediaResources();
        mediaRecorderRef.current = null;
      };

      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });

        audioChunksRef.current = [];
        mediaRecorderRef.current = null;

        void transcribeRecording(blob);
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);

      startSilenceDetection(stream);

      maxDurationTimeoutRef.current = setTimeout(() => {
        if (mediaRecorderRef.current?.state === "recording") {
          stopRecording();
        }
      }, MAX_RECORDING_MS);
    } catch {
      setSpeechError("Unable to access microphone. Please check permissions.");
      cleanupMediaResources();
      setIsRecording(false);
    }
  };

  const handleMicClick = async () => {
    if (isTranscribing || isLoading) {
      return;
    }

    if (isRecording) {
      stopRecording();
      return;
    }

    await startRecording();
  };

  const inputDisabled = isLoading || isTranscribing || isRecording;

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="relative bg-card border border-border rounded-2xl overflow-hidden transition-all duration-200 focus-within:border-primary/50 focus-within:glow-subtle">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Share your thoughts..."
          rows={1}
          className="w-full bg-transparent px-5 py-4 pr-24 text-sm resize-none focus:outline-none placeholder:text-muted-foreground/50"
          disabled={inputDisabled}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submitMessage(message);
            }
          }}
        />
        
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
          <button
            type="button"
            onClick={handleMicClick}
            disabled={isLoading || isTranscribing}
            className={cn(
              "p-2 rounded-lg transition-colors",
              isRecording
                ? "text-red-500 hover:text-red-400"
                : "text-muted-foreground hover:text-primary",
              (isLoading || isTranscribing) && "opacity-50 cursor-not-allowed"
            )}
            title={isRecording ? "Stop recording" : "Record voice message"}
          >
            {isTranscribing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : isRecording ? (
              <Square className="w-4 h-4" />
            ) : (
              <Mic className="w-4 h-4" />
            )}
          </button>
          <button
            type="submit"
            disabled={!message.trim() || inputDisabled}
            className={cn(
              "p-2.5 rounded-xl transition-all duration-200",
              message.trim() && !inputDisabled
                ? "bg-primary text-primary-foreground hover:opacity-90"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>

      {(isRecording || isTranscribing || speechError) && (
        <p className="text-center text-xs mt-2" role="status" aria-live="polite">
          {speechError ? (
            <span className="text-red-500">{speechError}</span>
          ) : isRecording ? (
            <span className="text-primary">Listening... tap again to stop</span>
          ) : (
            <span className="text-muted-foreground">Transcribing audio...</span>
          )}
        </p>
      )}

      <p className="text-center text-xs text-muted-foreground/50 mt-3">
        Reflectra adapts to your communication style and remembers context
      </p>
    </form>
  );
}
