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

export type SystemStats = { cpu: number; ram: number };

export type SystemAlert = {
  level?: string;
  resource?: "cpu" | "ram";
  message?: string;
};

export type ChatMessage = {
  role: "user" | "rocky";
  text: string;
  ts: number;
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
        const payload = { cpu, ram };
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

      await register<{ role: "user" | "rocky"; text: string }>(
        "rocky-chat",
        (payload) => {
          setChat((prev) => [...prev, { ...payload, ts: Date.now() }]);
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
  };
}
