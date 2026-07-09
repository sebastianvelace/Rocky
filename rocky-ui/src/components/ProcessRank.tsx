"use client";

import { useState } from "react";
import { Activity, Copy, Database, OctagonX } from "lucide-react";
import type { ProcessStats } from "../hooks/useRocky";

type Props = {
  topCpu?: ProcessStats[];
  topRam?: ProcessStats[];
};

function MetricBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-panel-2">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${Math.min(100, Math.max(0, value))}%`, background: color }}
      />
    </div>
  );
}

function RankList({
  title,
  icon,
  processes,
  metric,
  color,
  onCopyPid,
  onTerminate,
  busyPid,
  canTerminate,
}: {
  title: string;
  icon: React.ReactNode;
  processes: ProcessStats[];
  metric: "cpu" | "ram";
  color: string;
  onCopyPid: (process: ProcessStats) => void;
  onTerminate: (process: ProcessStats) => void;
  busyPid: string | null;
  canTerminate: boolean;
}) {
  return (
    <section className="min-w-0 rounded border border-edge bg-panel p-4">
      <header className="mb-3 flex items-center gap-2 text-xs uppercase tracking-widest text-ink-muted">
        <span style={{ color }}>{icon}</span>
        {title}
      </header>

      {processes.length === 0 ? (
        <p className="text-sm text-ink-faint">Sin procesos relevantes.</p>
      ) : (
        <div className="space-y-3">
          {processes.map((process, index) => {
            const value = metric === "cpu" ? process.cpu : process.ram;
            const blockedReason =
              process.protection_reason ??
              (process.protected ? "proceso protegido" : null);
            const terminateDisabled =
              !canTerminate || Boolean(process.protected) || busyPid === process.pid;
            return (
              <div key={`${process.pid}-${process.name}-${index}`} className="min-w-0">
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <p className="min-w-0 truncate text-sm text-ink">
                    <span className="mr-2 text-ink-faint">{index + 1}</span>
                    {process.name}
                  </p>
                  <div className="flex shrink-0 items-center gap-2">
                    <p className="text-xs tabular-nums text-ink-muted">
                      {metric === "cpu"
                        ? `${process.cpu.toFixed(1)}%`
                        : `${process.ram.toFixed(1)}% · ${process.memory_mb.toFixed(0)} MB`}
                    </p>
                    <button
                      type="button"
                      title={`Copiar PID ${process.pid}`}
                      onClick={() => onCopyPid(process)}
                      className="flex h-6 w-6 items-center justify-center rounded border border-edge text-ink-muted transition hover:border-edge-bright hover:text-ink"
                    >
                      <Copy size={12} aria-hidden />
                      <span className="sr-only">Copiar PID</span>
                    </button>
                    <button
                      type="button"
                      title={
                        blockedReason
                          ? `No terminable: ${blockedReason}`
                          : canTerminate
                            ? `Terminar ${process.name} (${process.pid})`
                            : "Solo disponible dentro de Tauri"
                      }
                      onClick={() => onTerminate(process)}
                      disabled={terminateDisabled}
                      className="flex h-6 w-6 items-center justify-center rounded border border-edge text-alert transition hover:border-alert disabled:cursor-not-allowed disabled:opacity-35"
                    >
                      <OctagonX size={12} aria-hidden />
                      <span className="sr-only">Terminar proceso</span>
                    </button>
                  </div>
                </div>
                <MetricBar value={value} color={color} />
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

export function ProcessRank({ topCpu = [], topRam = [] }: Props) {
  const [status, setStatus] = useState<string | null>(null);
  const [busyPid, setBusyPid] = useState<string | null>(null);
  const canTerminate = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

  const copyPid = async (process: ProcessStats) => {
    try {
      await navigator.clipboard.writeText(process.pid);
      setStatus(`PID copiado: ${process.pid}`);
    } catch {
      setStatus(`PID ${process.pid}`);
    }
  };

  const terminate = async (process: ProcessStats) => {
    if (!canTerminate) return;
    if (process.protected) {
      setStatus(`No terminable: ${process.protection_reason ?? "proceso protegido"}.`);
      return;
    }
    const confirmed = window.confirm(
      `Terminar ${process.name} (PID ${process.pid})?\n\nEsto enviará una señal de cierre al proceso seleccionado.`
    );
    if (!confirmed) return;

    setBusyPid(process.pid);
    setStatus(null);
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const result = await invoke<string>("terminate_process", {
        pid: process.pid,
        expectedName: process.name,
      });
      setStatus(result);
    } catch (error) {
      setStatus(String(error));
    } finally {
      setBusyPid(null);
    }
  };

  return (
    <section className="space-y-2">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RankList
          title="Top procesos CPU"
          icon={<Activity size={14} aria-hidden />}
          processes={topCpu}
          metric="cpu"
          color="#16a34a"
          onCopyPid={copyPid}
          onTerminate={terminate}
          busyPid={busyPid}
          canTerminate={canTerminate}
        />
        <RankList
          title="Top procesos RAM"
          icon={<Database size={14} aria-hidden />}
          processes={topRam}
          metric="ram"
          color="#0284c7"
          onCopyPid={copyPid}
          onTerminate={terminate}
          busyPid={busyPid}
          canTerminate={canTerminate}
        />
      </div>
      {status ? <p className="text-xs text-ink-muted">{status}</p> : null}
    </section>
  );
}
