"use client";

import { useMemo, useState } from "react";
import { TriangleAlert } from "lucide-react";
import { HISTORY_LENGTH } from "../hooks/useRocky";

type Props = {
  label: string;
  icon: React.ReactNode;
  value: number;
  history: number[];
  color: string;
  threshold: number;
};

const W = 240;
const H = 56;
const PAD_Y = 4;

function y(value: number): number {
  const clamped = Math.min(100, Math.max(0, value));
  return H - PAD_Y - (clamped / 100) * (H - PAD_Y * 2);
}

/**
 * Tarjeta de métrica: valor grande + barra de uso + sparkline (últimos 60 s)
 * con hover para leer valores puntuales. Un solo eje 0–100 %.
 */
export function StatGauge({ label, icon, value, history, color, threshold }: Props) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const points = useMemo(() => {
    if (history.length < 2) return "";
    const step = W / (HISTORY_LENGTH - 1);
    const offset = HISTORY_LENGTH - history.length;
    return history
      .map((v, i) => `${((offset + i) * step).toFixed(1)},${y(v).toFixed(1)}`)
      .join(" ");
  }, [history]);

  const areaPoints = useMemo(() => {
    if (!points) return "";
    const step = W / (HISTORY_LENGTH - 1);
    const offset = HISTORY_LENGTH - history.length;
    const x0 = (offset * step).toFixed(1);
    return `${x0},${H - PAD_Y} ${points} ${W},${H - PAD_Y}`;
  }, [points, history.length]);

  const overThreshold = value > threshold;

  const hovered =
    hoverIndex !== null && hoverIndex >= 0 && hoverIndex < history.length
      ? history[hoverIndex]
      : null;

  const handleMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (history.length < 2) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const relX = ((e.clientX - rect.left) / rect.width) * W;
    const step = W / (HISTORY_LENGTH - 1);
    const offset = HISTORY_LENGTH - history.length;
    const idx = Math.round(relX / step) - offset;
    setHoverIndex(idx >= 0 && idx < history.length ? idx : null);
  };

  const step = W / (HISTORY_LENGTH - 1);
  const offset = HISTORY_LENGTH - history.length;

  return (
    <section className="border-t border-edge pt-3">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-ink-muted">
          <span style={{ color }}>{icon}</span>
          {label}
        </div>
        {overThreshold ? (
          <span className="flex items-center gap-1 text-xs font-semibold text-warn">
            <TriangleAlert size={13} aria-hidden />
            sobre umbral
          </span>
        ) : null}
      </header>

      <p className="mt-2 text-4xl font-bold tabular-nums text-ink">
        {value.toFixed(1)}
        <span className="ml-1 text-base font-normal text-ink-faint">%</span>
      </p>

      {/* Barra de uso con marca de umbral */}
      <div className="relative mt-3 h-1.5 w-full overflow-hidden bg-panel-2">
        <div
          className="h-full transition-all duration-500"
          style={{ width: `${Math.min(100, value)}%`, background: color }}
        />
        <div
          className="absolute top-0 h-full w-px bg-ink-faint"
          style={{ left: `${threshold}%` }}
          title={`Umbral de alerta: ${threshold}%`}
        />
      </div>

      {/* Sparkline: últimos 60 segundos */}
      <div className="mt-3">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-14 w-full"
          role="img"
          aria-label={`Historial de ${label}: ${
            history.length ? history[history.length - 1].toFixed(1) : 0
          }% actual`}
          onMouseMove={handleMove}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <line
            x1="0"
            x2={W}
            y1={y(threshold)}
            y2={y(threshold)}
            stroke="var(--color-ink-faint)"
            strokeWidth="1"
            strokeDasharray="3 4"
            opacity="0.6"
          />
          {areaPoints ? (
            <polygon points={areaPoints} fill={color} opacity="0.14" />
          ) : null}
          {points ? (
            <polyline
              points={points}
              fill="none"
              stroke={color}
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ) : null}
          {hovered !== null && hoverIndex !== null ? (
            <>
              <line
                x1={(offset + hoverIndex) * step}
                x2={(offset + hoverIndex) * step}
                y1={PAD_Y}
                y2={H - PAD_Y}
                stroke="var(--color-ink-muted)"
                strokeWidth="1"
                opacity="0.5"
              />
              <circle
                cx={(offset + hoverIndex) * step}
                cy={y(hovered)}
                r="3.5"
                fill={color}
                stroke="var(--color-surface)"
                strokeWidth="2"
              />
            </>
          ) : null}
        </svg>
        <p className="mt-1 flex justify-between text-[10px] text-ink-faint">
          <span>-{Math.max(history.length - 1, 0)} s</span>
          <span className="tabular-nums">
            {hovered !== null
              ? `${hovered.toFixed(1)}% hace ${history.length - 1 - (hoverIndex ?? 0)} s`
              : "ahora"}
          </span>
        </p>
      </div>
    </section>
  );
}
