"use client"; // Obligatorio

import { useEffect, useState } from "react";

type SystemAlertPayload = {
  type?: string;
  level?: string;
  message?: string;
};

export default function Page() {
  const [stats, setStats] = useState({ cpu: 0, ram: 0 });
  const [isAlerting, setIsAlerting] = useState(false);
  const [alertMessage, setAlertMessage] = useState<string | null>(null);

  useEffect(() => {
    const setupTelemetry = async () => {
      const { listen } = await import("@tauri-apps/api/event");

      const unlisten = await listen<{ cpu: number; ram: number }>(
        "system-stats",
        (event) => {
          setStats(event.payload);
        }
      );

      return unlisten;
    };

    const unlistenPromise = setupTelemetry();

    return () => {
      unlistenPromise.then((unlisten) => unlisten());
    };
  }, []);

  useEffect(() => {
    let disposed = false;
    let unlisten: (() => void) | undefined;
    let alertTimeout: ReturnType<typeof setTimeout> | undefined;

    void (async () => {
      const { listen } = await import("@tauri-apps/api/event");
      if (disposed) return;
      unlisten = await listen<SystemAlertPayload>("system-alert", (event) => {
        const msg =
          typeof event.payload?.message === "string"
            ? event.payload.message
            : "Alerta del sistema";
        setAlertMessage(msg);
        setIsAlerting(true);
        if (alertTimeout) clearTimeout(alertTimeout);
        alertTimeout = setTimeout(() => {
          setIsAlerting(false);
          setAlertMessage(null);
        }, 4000);
      });
    })();

    return () => {
      disposed = true;
      if (alertTimeout) clearTimeout(alertTimeout);
      unlisten?.();
    };
  }, []);

  return (
    <main
      className={`min-h-screen p-10 font-mono transition-colors duration-300 ${
        isAlerting
          ? "animate-pulse border-4 border-red-700 bg-[#1a0505] text-red-100 shadow-[0_0_40px_rgba(220,38,38,0.45)]"
          : "border border-transparent bg-black text-green-400"
      }`}
    >
      <h1>ROCKY TELEMETRY</h1>
      {alertMessage ? (
        <p className="mt-2 max-w-xl rounded border border-red-500/60 bg-red-950/80 px-3 py-2 text-sm font-semibold text-red-100">
          {alertMessage}
        </p>
      ) : null}
      <div className="mt-4">
        <p>CPU: {stats.cpu.toFixed(1)}%</p>
        <div className="h-4 w-full bg-gray-800">
          <div
            className="h-full bg-green-500 transition-all duration-300"
            style={{ width: `${stats.cpu}%` }}
          />
        </div>
      </div>
      <div className="mt-4">
        <p>RAM: {stats.ram.toFixed(1)}%</p>
        <div className="h-4 w-full bg-gray-800">
          <div
            className="h-full bg-blue-500 transition-all duration-300"
            style={{ width: `${stats.ram}%` }}
          />
        </div>
      </div>
    </main>
  );
}
