"use client";

import { memo } from "react";
import { ListTree } from "lucide-react";
import type { ProcessStat } from "../hooks/useRocky";

function formatMem(mb: number): string {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`;
}

/** Top de procesos en vivo (agregados por nombre desde Rust). */
function TopProcessesBase({ top }: { top: ProcessStat[] }) {
  return (
    <section className="rounded border border-edge bg-panel p-4">
      <header className="flex items-center gap-2 text-xs uppercase tracking-widest text-ink-muted">
        <ListTree size={14} aria-hidden />
        Procesos
      </header>

      {top.length === 0 ? (
        <p className="mt-3 text-xs text-ink-faint">Esperando datos de procesos…</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {top.map((p) => (
            <li key={p.name} className="text-xs">
              <div className="flex items-baseline justify-between gap-2">
                <span className="min-w-0 truncate text-ink" title={p.name}>
                  {p.name}
                </span>
                <span className="shrink-0 tabular-nums text-ink-muted">
                  {p.cpu.toFixed(0)}%
                  <span className="text-ink-faint"> · {formatMem(p.mem_mb)}</span>
                </span>
              </div>
              <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-panel-2">
                <div
                  className="h-full rounded-full bg-ink-muted/70 transition-all duration-500"
                  style={{ width: `${Math.min(100, p.cpu)}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export const TopProcesses = memo(TopProcessesBase);
