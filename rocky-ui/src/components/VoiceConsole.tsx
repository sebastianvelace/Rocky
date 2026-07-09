"use client";

import { memo, useEffect, useRef, useState } from "react";
import { CornerDownLeft, Mic } from "lucide-react";
import type { ChatMessage, VoiceState } from "../hooks/useRocky";
import { RockyAvatar } from "./RockyAvatar";
import { TypewriterText } from "./TypewriterText";

type Props = {
  chat: ChatMessage[];
  voiceState: VoiceState;
  voiceDetail: string | null;
  voiceBusy: boolean;
  alerting: boolean;
  onListen: () => void;
  onSend: (text: string) => void;
};

const STATE_LABEL: Record<VoiceState, string> = {
  idle: "en espera",
  listening: "escuchando…",
  transcribing: "transcribiendo…",
  thinking: "pensando…",
  speaking: "hablando…",
  error: "error",
};

function VoiceConsoleBase({
  chat,
  voiceState,
  voiceDetail,
  voiceBusy,
  alerting,
  onListen,
  onSend,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chat, voiceState]);

  // Devolver el foco al input cuando Rocky termina de trabajar.
  useEffect(() => {
    if (!voiceBusy) inputRef.current?.focus();
  }, [voiceBusy]);

  const submit = () => {
    if (voiceBusy || !draft.trim()) return;
    onSend(draft);
    setDraft("");
  };

  const lastIndex = chat.length - 1;

  return (
    <section className="flex min-h-0 flex-1 flex-col border-y border-edge bg-panel">
      <header className="flex items-center justify-between border-b border-edge px-4 py-2.5">
        <div className="flex items-center gap-3">
          <RockyAvatar state={voiceState} alerting={alerting} size={40} />
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-ink">Rocky</p>
            <p
              className={`text-xs ${
                voiceState === "error"
                  ? "text-ink"
                  : voiceBusy
                    ? "text-ink"
                    : "text-ink-faint"
              }`}
            >
              {STATE_LABEL[voiceState]}
              {voiceState === "error" && voiceDetail ? ` — ${voiceDetail}` : ""}
            </p>
          </div>
        </div>
      </header>

      <div
        ref={scrollRef}
        className="rocky-scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3"
      >
        {chat.length === 0 ? (
          <p className="text-sm text-ink-faint">
            Escribe abajo o pulsa el micrófono. La conversación con Rocky aparecerá aquí.
          </p>
        ) : (
          chat.map((msg, i) => (
            <div key={`${msg.ts}-${i}`} className="rocky-rise text-sm leading-relaxed">
              <span
                className={
                  msg.role === "rocky"
                    ? "font-semibold text-accent"
                    : "font-semibold text-ink-muted"
                }
              >
                {msg.role === "rocky" ? "rocky" : "sebas"}@core:~$
              </span>{" "}
              <span className="text-ink">
                {msg.role === "rocky" ? (
                  <>
                    <TypewriterText
                      text={msg.text}
                      // El streaming ya "escribe" en vivo; el typewriter es
                      // solo para mensajes que llegan de una pieza.
                      animate={i === lastIndex && !msg.streaming && !msg.streamed}
                    />
                    {msg.streaming ? <span className="rocky-caret" aria-hidden /> : null}
                  </>
                ) : (
                  msg.text
                )}
              </span>
            </div>
          ))
        )}
        {voiceState === "thinking" ? (
          <div className="rocky-rise text-sm">
            <span className="font-semibold text-accent">rocky@core:~$</span>{" "}
            <span className="rocky-caret" aria-label="Rocky está pensando" />
          </div>
        ) : null}
      </div>

      <footer className="flex items-center gap-2 border-t border-edge px-3 py-2.5">
        <button
          type="button"
          onClick={onListen}
          disabled={voiceBusy}
          title="Hablar con Rocky (micrófono)"
          className={`flex h-10 w-10 shrink-0 items-center justify-center border transition disabled:cursor-not-allowed disabled:opacity-40 ${
            voiceState === "listening"
              ? "border-ink bg-ink text-surface"
              : "border-edge bg-panel-2 text-ink hover:border-ink"
          }`}
        >
          <Mic size={16} className={voiceState === "listening" ? "rocky-blink" : ""} aria-hidden />
          <span className="sr-only">Hablar</span>
        </button>

        <div className="flex h-10 min-w-0 flex-1 items-center gap-2 border border-edge bg-surface px-3 focus-within:border-ink">
          <span className="shrink-0 text-sm font-semibold text-ink-muted">&gt;</span>
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
            }}
            disabled={voiceBusy}
            placeholder={voiceBusy ? STATE_LABEL[voiceState] : "escríbele a rocky…"}
            className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint disabled:cursor-not-allowed"
            aria-label="Mensaje para Rocky"
          />
        </div>

        <button
          type="button"
          onClick={submit}
          disabled={voiceBusy || !draft.trim()}
          title="Enviar (Enter)"
          className="flex h-10 w-10 shrink-0 items-center justify-center border border-edge bg-panel-2 text-ink transition hover:bg-ink hover:text-surface disabled:cursor-not-allowed disabled:opacity-40"
        >
          <CornerDownLeft size={16} aria-hidden />
          <span className="sr-only">Enviar</span>
        </button>
      </footer>
    </section>
  );
}

export const VoiceConsole = memo(VoiceConsoleBase);
