"use client";

import { Cpu, MemoryStick } from "lucide-react";
import { AlertBanner } from "../components/AlertBanner";
import { StatGauge } from "../components/StatGauge";
import { VoiceConsole } from "../components/VoiceConsole";
import { useRocky } from "../hooks/useRocky";

const CPU_COLOR = "#16a34a";
const RAM_COLOR = "#0284c7";
const CPU_THRESHOLD = 80;
const RAM_THRESHOLD = 90;

export default function Page() {
  const {
    connected,
    demoMode,
    stats,
    cpuHistory,
    ramHistory,
    alert,
    chat,
    voiceState,
    voiceDetail,
    voiceBusy,
    startListening,
  } = useRocky();

  return (
    <main className="mx-auto flex h-screen max-w-5xl flex-col gap-4 p-6">
      <header className="flex items-center justify-between border-b border-edge pb-4">
        <h1 className="text-sm font-bold uppercase tracking-[0.3em] text-accent">
          Rocky <span className="text-ink-faint">//</span> Telemetry Core
        </h1>
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <span
            className={`h-2 w-2 rounded-full ${
              connected
                ? "bg-accent"
                : demoMode
                  ? "bg-warn"
                  : "bg-ink-faint rocky-blink"
            }`}
            aria-hidden
          />
          {connected
            ? "telemetría activa"
            : demoMode
              ? "modo demo (sin Tauri)"
              : "esperando telemetría…"}
        </div>
      </header>

      <AlertBanner alert={alert} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatGauge
          label="CPU"
          icon={<Cpu size={14} aria-hidden />}
          value={stats.cpu}
          history={cpuHistory}
          color={CPU_COLOR}
          threshold={CPU_THRESHOLD}
        />
        <StatGauge
          label="RAM"
          icon={<MemoryStick size={14} aria-hidden />}
          value={stats.ram}
          history={ramHistory}
          color={RAM_COLOR}
          threshold={RAM_THRESHOLD}
        />
      </div>

      <VoiceConsole
        chat={chat}
        voiceState={voiceState}
        voiceDetail={voiceDetail}
        voiceBusy={voiceBusy}
        onListen={startListening}
      />
    </main>
  );
}
