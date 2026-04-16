"use client"; // Obligatorio

import { useEffect, useState } from "react";

export default function Page() {
  const [stats, setStats] = useState({ cpu: 0, ram: 0 });

  useEffect(() => {
    // IMPORT DINÁMICO: Esto evita que Next.js explote en el servidor
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

    // Limpieza al desmontar
    return () => {
      unlistenPromise.then((unlisten) => unlisten());
    };
  }, []);

  return (
    <main className="p-10 font-mono">
      <h1>ROCKY TELEMETRY</h1>
      <div className="mt-4">
        <p>CPU: {stats.cpu.toFixed(1)}%</p>
        <div className="w-full bg-gray-800 h-4">
          <div
            className="bg-green-500 h-full transition-all duration-300"
            style={{ width: `${stats.cpu}%` }}
          />
        </div>
      </div>
      <div className="mt-4">
        <p>RAM: {stats.ram.toFixed(1)}%</p>
        <div className="w-full bg-gray-800 h-4">
          <div
            className="bg-blue-500 h-full transition-all duration-300"
            style={{ width: `${stats.ram}%` }}
          />
        </div>
      </div>
    </main>
  );
}
