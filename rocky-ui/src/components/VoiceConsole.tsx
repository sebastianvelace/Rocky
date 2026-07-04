"use client";

import { useEffect, useRef } from "react";
import { Loader2, Mic, Terminal, Volume2 } from "lucide-react";
import type { ChatMessage, VoiceState } from "../hooks/useRocky";

type Props = {
  chat: ChatMessage[];
  voiceState: VoiceState;
  voiceDetail: string | null;
  voiceBusy: boolean;
  onListen: () => void;
};

const STATE_LABEL: Record<VoiceState, string> = {
  idle: "En espera",
  listening: "Escuchando…",
  transcribing: "Transcribiendo…",
  thinking: "Pensando…",
  speaking: "Hablando…",
  error: "Error",
};

export function VoiceConsole({ chat, voiceState, voiceDetail, voiceBusy, onListen }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [chat, voiceState]);

  return (
    <section className="flex min-h-0 flex-1 flex-col rounded border border-edge bg-panel">
      <header className="flex items-center justify-between border-b border-edge px-4 py-3">
        <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-ink-muted">
          <Terminal size={14} aria-hidden />
          Consola de voz
        </div>
        <span
          className={`text-xs ${
            voiceState === "error"
              ? "text-alert"
              : voiceBusy
                ? "text-accent rocky-blink"
                : "text-ink-faint"
          }`}
        >
          {STATE_LABEL[voiceState]}
          {voiceState === "error" && voiceDetail ? ` — ${voiceDetail}` : ""}
        </span>
      </header>

      <div
        ref={scrollRef}
        className="rocky-scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3"
      >
        {chat.length === 0 ? (
          <p className="text-sm text-ink-faint">
            Pulsa <span className="text-accent">Hablar</span> y dile algo a Rocky.
            La transcripción y su respuesta aparecerán aquí.
          </p>
        ) : (
          chat.map((msg, i) => (
            <div key={`${msg.ts}-${i}`} className="text-sm leading-relaxed">
              <span
                className={
                  msg.role === "rocky" ? "font-semibold text-accent" : "font-semibold text-ink-muted"
                }
              >
                {msg.role === "rocky" ? "rocky" : "sebas"}@core:~$
              </span>{" "}
              <span className="text-ink">{msg.text}</span>
            </div>
          ))
        )}
      </div>

      <footer className="border-t border-edge px-4 py-3">
        <button
          type="button"
          onClick={onListen}
          disabled={voiceBusy}
          className="flex w-full items-center justify-center gap-2 rounded border border-edge-bright bg-panel-2 px-4 py-2.5 text-sm font-semibold text-accent transition hover:border-accent hover:bg-panel disabled:cursor-not-allowed disabled:opacity-50"
        >
          {voiceState === "listening" ? (
            <Mic size={16} className="rocky-blink" aria-hidden />
          ) : voiceState === "speaking" ? (
            <Volume2 size={16} aria-hidden />
          ) : voiceBusy ? (
            <Loader2 size={16} className="animate-spin" aria-hidden />
          ) : (
            <Mic size={16} aria-hidden />
          )}
          {voiceBusy ? STATE_LABEL[voiceState] : "Hablar"}
        </button>
      </footer>
    </section>
  );
}
