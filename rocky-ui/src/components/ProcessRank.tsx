"use client";

import { Activity, Database } from "lucide-react";
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
}: {
  title: string;
  icon: React.ReactNode;
  processes: ProcessStats[];
  metric: "cpu" | "ram";
  color: string;
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
            return (
              <div key={`${process.pid}-${process.name}-${index}`} className="min-w-0">
                <div className="mb-1 flex items-baseline justify-between gap-3">
                  <p className="min-w-0 truncate text-sm text-ink">
                    <span className="mr-2 text-ink-faint">{index + 1}</span>
                    {process.name}
                  </p>
                  <p className="shrink-0 text-xs tabular-nums text-ink-muted">
                    {metric === "cpu"
                      ? `${process.cpu.toFixed(1)}%`
                      : `${process.ram.toFixed(1)}% · ${process.memory_mb.toFixed(0)} MB`}
                  </p>
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
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <RankList
        title="Top procesos CPU"
        icon={<Activity size={14} aria-hidden />}
        processes={topCpu}
        metric="cpu"
        color="#16a34a"
      />
      <RankList
        title="Top procesos RAM"
        icon={<Database size={14} aria-hidden />}
        processes={topRam}
        metric="ram"
        color="#0284c7"
      />
    </div>
  );
}
