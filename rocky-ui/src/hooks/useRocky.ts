"use client";

/**
 * Estado del asistente Rocky en el frontend.
 *
 * Escucha los eventos que emite el proceso Rust (Tauri):
 *  - `system-stats`  → telemetría {cpu, ram} cada segundo
 *  - `system-alert`  → alerta de sobrecarga con consejo de la IA
 *  - `rocky-chat`    → turnos de conversación (transcripción / respuesta)
 *  - `voice-state`   → estado del pipeline de voz en el engine
 *
 * Fuera de Tauri (npm run dev en navegador) no hay eventos: el hook entra
 * en modo demo con telemetría simulada, claramente etiquetada en la UI,
 * para poder iterar el diseño sin compilar la app nativa.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export const HISTORY_LENGTH = 60;

export type ProcessStats = {
  pid: string;
  name: string;
  cpu: number;
  ram: number;
  memory_mb: number;
  protected?: boolean;
  protection_reason?: string | null;
};

export type SystemStats = {
  cpu: number;
  ram: number;
  top_cpu?: ProcessStats[];
  top_ram?: ProcessStats[];
};

export type SystemAlert = {
  level?: string;
  resource?: "cpu" | "ram";
  message?: string;
};

export type ChatMessage = {
  role: "user" | "rocky";
  text: string;
  ts: number;
  /** El mensaje está llegando en deltas de streaming (mostrar cursor). */
  streaming?: boolean;
  /** El mensaje llegó por streaming: no re-animarlo con typewriter. */
  streamed?: boolean;
};

export type VoiceState =
  | "idle"
  | "listening"
  | "transcribing"
  | "thinking"
  | "speaking"
  | "error";

const ALERT_VISIBLE_MS = 8000;
const VOICE_SAFETY_TIMEOUT_MS = 15000;

const DEMO_REPLIES = [
  "Modo demo, Sebas: sin engine no hay Llama, pero el teclado se siente bien, ¿no?",
  "Te escucho perfectamente… es broma, soy una respuesta simulada del modo demo.",
  "En la app real esto lo respondería Llama 3.3 con tu telemetría en contexto.",
  "Todo nominal por aquí. Bueno, todo simulado, pero nominal.",
];

const DEMO_PROCESSES = [
  { pid: "2142", name: "next-dev", cpu: 18, ram: 4.2, memory_mb: 520 },
  { pid: "2198", name: "rust-analyzer", cpu: 11, ram: 3.6, memory_mb: 450 },
  { pid: "2050", name: "code", cpu: 7, ram: 8.1, memory_mb: 990 },
  {
    pid: "2281",
    name: "uvicorn",
    cpu: 4,
    ram: 1.5,
    memory_mb: 180,
    protected: true,
    protection_reason: "proceso interno de Rocky",
  },
  { pid: "1888", name: "firefox", cpu: 3, ram: 11.2, memory_mb: 1360 },
];

function demoProcesses(cpu: number, ram: number): Pick<SystemStats, "top_cpu" | "top_ram"> {
  const topCpu = DEMO_PROCESSES.map((process, index) => ({
    ...process,
    cpu: Math.max(0, process.cpu + (Math.random() - 0.5) * (index === 0 ? 8 : 3)),
    ram: Math.max(0.1, process.ram + (Math.random() - 0.5) * 0.8),
  }))
    .sort((a, b) => b.cpu - a.cpu)
    .slice(0, 5);
  const topRam = DEMO_PROCESSES.map((process) => ({
    ...process,
    memory_mb: Math.max(30, process.memory_mb + (Math.random() - 0.5) * 80),
    ram: Math.max(0.1, process.ram + (ram / 100) * 0.6),
    cpu: Math.max(0, process.cpu + (cpu / 100) * 1.5),
  }))
    .sort((a, b) => b.memory_mb - a.memory_mb)
    .slice(0, 5);
  return { top_cpu: topCpu, top_ram: topRam };
}

function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function useRocky() {
  const [connected, setConnected] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const [stats, setStats] = useState<SystemStats>({ cpu: 0, ram: 0 });
  const [cpuHistory, setCpuHistory] = useState<number[]>([]);
  const [ramHistory, setRamHistory] = useState<number[]>([]);
  const [alert, setAlert] = useState<SystemAlert | null>(null);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [voiceDetail, setVoiceDetail] = useState<string | null>(null);

  const alertTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const voiceSafetyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!isTauri()) {
      // Modo demo (navegador): random walk plausible para iterar el diseño.
      setDemoMode(true);
      let cpu = 35;
      let ram = 55;
      const tick = () => {
        cpu = Math.min(98, Math.max(2, cpu + (Math.random() - 0.5) * 14));
        ram = Math.min(98, Math.max(10, ram + (Math.random() - 0.5) * 4));
        const payload = { cpu, ram, ...demoProcesses(cpu, ram) };
        setStats(payload);
        setCpuHistory((prev) => [...prev, payload.cpu].slice(-HISTORY_LENGTH));
        setRamHistory((prev) => [...prev, payload.ram].slice(-HISTORY_LENGTH));
      };
      tick();
      const interval = setInterval(tick, 1000);
      return () => clearInterval(interval);
    }

    let disposed = false;
    const unlisteners: Array<() => void> = [];

    void (async () => {
      const { listen } = await import("@tauri-apps/api/event");
      if (disposed) return;

      const register = async <T,>(
        event: string,
        handler: (payload: T) => void
      ) => {
        const un = await listen<T>(event, (e) => handler(e.payload));
        if (disposed) un();
        else unlisteners.push(un);
      };

      await register<SystemStats>("system-stats", (payload) => {
        setConnected(true);
        setStats(payload);
        setCpuHistory((prev) => [...prev, payload.cpu].slice(-HISTORY_LENGTH));
        setRamHistory((prev) => [...prev, payload.ram].slice(-HISTORY_LENGTH));
      });

      await register<SystemAlert>("system-alert", (payload) => {
        setAlert(payload);
        if (alertTimer.current) clearTimeout(alertTimer.current);
        alertTimer.current = setTimeout(() => setAlert(null), ALERT_VISIBLE_MS);
      });

      await register<{ role: "user" | "rocky"; text: string; partial?: boolean }>(
        "rocky-chat",
        (payload) => {
          setChat((prev) => {
            const last = prev[prev.length - 1];
            const lastIsStream =
              last?.role === "rocky" && last.streaming === true;

            if (payload.role === "rocky" && payload.partial) {
              // Delta de streaming: anexar al mensaje en curso (o abrir uno).
              if (lastIsStream) {
                return [
                  ...prev.slice(0, -1),
                  { ...last, text: last.text + payload.text },
                ];
              }
              return [
                ...prev,
                { role: "rocky", text: payload.text, ts: Date.now(), streaming: true },
              ];
            }

            if (payload.role === "rocky" && lastIsStream) {
              // Evento final: texto completo, cierra el mensaje en curso.
              return [
                ...prev.slice(0, -1),
                { role: "rocky", text: payload.text, ts: last.ts, streamed: true },
              ];
            }

            return [...prev, { role: payload.role, text: payload.text, ts: Date.now() }];
          });
        }
      );

      await register<{ state: VoiceState; detail?: string | null }>(
        "voice-state",
        (payload) => {
          if (voiceSafetyTimer.current) {
            clearTimeout(voiceSafetyTimer.current);
            voiceSafetyTimer.current = null;
          }
          setVoiceState(payload.state);
          setVoiceDetail(payload.detail ?? null);
        }
      );
    })();

    return () => {
      disposed = true;
      unlisteners.forEach((un) => un());
      if (alertTimer.current) clearTimeout(alertTimer.current);
      if (voiceSafetyTimer.current) clearTimeout(voiceSafetyTimer.current);
    };
  }, []);

  const startListening = useCallback(async () => {
    if (!isTauri()) {
      setVoiceState("error");
      setVoiceDetail("Solo disponible dentro de la app Tauri");
      return;
    }

    setVoiceState("listening");
    setVoiceDetail(null);
    // Red de seguridad: si el engine no responde (caído, sin micrófono),
    // no dejamos el botón bloqueado para siempre.
    voiceSafetyTimer.current = setTimeout(() => {
      setVoiceState("error");
      setVoiceDetail("El engine no respondió");
    }, VOICE_SAFETY_TIMEOUT_MS);

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("request_listen");
    } catch (err) {
      if (voiceSafetyTimer.current) clearTimeout(voiceSafetyTimer.current);
      setVoiceState("error");
      setVoiceDetail(String(err));
    }
  }, []);

  const sendChat = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    if (!isTauri()) {
      // Demo: respuesta simulada para poder sentir la interacción en navegador.
      setChat((prev) => [...prev, { role: "user", text: trimmed, ts: Date.now() }]);
      setVoiceState("thinking");
      setTimeout(() => {
        const reply = DEMO_REPLIES[Math.floor(Math.random() * DEMO_REPLIES.length)];
        setChat((prev) => [...prev, { role: "rocky", text: reply, ts: Date.now() }]);
        setVoiceState("idle");
      }, 900);
      return;
    }

    // El engine hace eco del turno del usuario y de la respuesta vía
    // eventos `rocky-chat`; aquí solo mostramos el estado optimista.
    setVoiceState("thinking");
    setVoiceDetail(null);
    voiceSafetyTimer.current = setTimeout(() => {
      setVoiceState("error");
      setVoiceDetail("El engine no respondió");
    }, VOICE_SAFETY_TIMEOUT_MS);

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("send_chat", { text: trimmed });
    } catch (err) {
      if (voiceSafetyTimer.current) clearTimeout(voiceSafetyTimer.current);
      setVoiceState("error");
      setVoiceDetail(String(err));
    }
  }, []);

  const voiceBusy = voiceState !== "idle" && voiceState !== "error";

  return {
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
    sendChat,
  };
}
