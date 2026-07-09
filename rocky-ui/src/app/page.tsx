"use client";

import { Cpu, MemoryStick } from "lucide-react";
import { AlertBanner } from "../components/AlertBanner";
import { ModelSwitcher } from "../components/ModelSwitcher";
import { ProcessRank } from "../components/ProcessRank";
import { StatGauge } from "../components/StatGauge";
import { VoiceConsole } from "../components/VoiceConsole";
import { useRocky } from "../hooks/useRocky";

const CPU_COLOR = "#0a0a0a";
const RAM_COLOR = "#525252";
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
    modelStatus,
    startListening,
    sendChat,
    refreshModels,
    selectModel,
  } = useRocky();

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-[1400px] flex-col px-5 py-5 sm:px-8 sm:py-7">
      <header className="flex items-center justify-between gap-4 border-b-2 border-ink pb-3">
        <h1 className="text-sm font-bold uppercase tracking-[0.2em] text-ink">
          Rocky <span className="text-ink-faint">/</span> Core
        </h1>
        <div className="flex items-center gap-4">
          <ModelSwitcher status={modelStatus} demoMode={demoMode} onRefresh={refreshModels} onSelect={selectModel} />
          <div className="hidden items-center gap-2 text-xs text-ink-muted sm:flex">
          <span
            className={`h-2 w-2 rounded-full ${
              connected
                ? "bg-ink"
                : demoMode
                  ? "bg-ink-muted"
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
        </div>
      </header>

      <div className="mt-4"><AlertBanner alert={alert} /></div>

      <div className="mt-7 grid grid-cols-1 gap-x-10 gap-y-6 sm:grid-cols-2">
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

      <div className="mt-8"><ProcessRank topCpu={stats.top_cpu} topRam={stats.top_ram} /></div>

      <div className="mt-8 min-h-[360px] flex-1">
        <VoiceConsole chat={chat} voiceState={voiceState} voiceDetail={voiceDetail} voiceBusy={voiceBusy} alerting={Boolean(alert)} onListen={startListening} onSend={sendChat} />
      </div>
    </main>
  );
}
