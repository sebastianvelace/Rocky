"use client";

import { TriangleAlert } from "lucide-react";
import type { SystemAlert } from "../hooks/useRocky";

export function AlertBanner({ alert }: { alert: SystemAlert | null }) {
  if (!alert || !alert.message) return null;

  return (
    <div
      role="alert"
      className="rocky-rise flex items-start gap-3 rounded border border-alert/60 bg-alert/10 px-4 py-3"
    >
      <TriangleAlert className="mt-0.5 shrink-0 text-alert" size={18} aria-hidden />
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-alert">
          Alerta {alert.resource ? `de ${alert.resource}` : "del sistema"}
        </p>
        <p className="mt-1 text-sm text-ink">{alert.message}</p>
      </div>
    </div>
  );
}
