"use client";

import { RefreshCw } from "lucide-react";
import type { ModelStatus } from "../hooks/useRocky";

type Props = {
  status: ModelStatus;
  demoMode: boolean;
  onRefresh: () => void;
  onSelect: (model: string) => void;
};

function modelLabel(model: ModelStatus["models"][number]) {
  const details = [model.parameter_size, model.quantization, model.loaded ? "RAM" : null].filter(Boolean).join(" · ");
  return details ? `${model.id} (${details})` : model.id;
}

export function ModelSwitcher({ status, demoMode, onRefresh, onSelect }: Props) {
  const selected = status.provider === "ollama" ? status.active_model ?? "" : "";
  const unavailable = demoMode || status.models.length === 0;
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <label className="sr-only" htmlFor="ollama-model">Modelo activo</label>
      <select id="ollama-model" value={selected} disabled={unavailable} onChange={(event) => onSelect(event.target.value)} title={status.detail ?? "Seleccionar modelo local de Ollama"} className="h-8 max-w-52 truncate border-b border-edge bg-transparent px-1 text-xs font-medium text-ink outline-none transition focus:border-ink disabled:text-ink-faint">
        <option value="">{status.provider === "groq" ? "Groq activo" : unavailable ? "Ollama no disponible" : "Modelo local"}</option>
        {status.models.map((model) => <option key={model.id} value={model.id}>{modelLabel(model)}</option>)}
      </select>
      <button type="button" onClick={onRefresh} title="Actualizar modelos de Ollama" className="flex h-8 w-8 items-center justify-center border border-edge text-ink transition hover:bg-ink hover:text-surface disabled:opacity-40" disabled={demoMode}>
        <RefreshCw size={14} strokeWidth={1.8} aria-hidden />
        <span className="sr-only">Actualizar modelos</span>
      </button>
    </div>
  );
}
