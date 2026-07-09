import { HardDrive, MonitorCog, Network, Thermometer } from "lucide-react";
import type { SystemStats } from "../hooks/useRocky";

function formatRate(rate: number) {
  return rate >= 1024 ? `${(rate / 1024).toFixed(1)} MB/s` : `${rate.toFixed(0)} KB/s`;
}

export function ResourceStrip({ stats }: { stats: SystemStats }) {
  const items = [
    { icon: <HardDrive size={14} aria-hidden />, label: "Disco", value: `${(stats.disk_used ?? 0).toFixed(0)}%` },
    { icon: <Network size={14} aria-hidden />, label: "Red", value: `↓ ${formatRate(stats.network_rx_kbps ?? 0)} · ↑ ${formatRate(stats.network_tx_kbps ?? 0)}` },
    { icon: <Thermometer size={14} aria-hidden />, label: "Temp.", value: stats.temperature_c == null ? "N/D" : `${stats.temperature_c.toFixed(0)} °C` },
    { icon: <MonitorCog size={14} aria-hidden />, label: "GPU", value: stats.gpu_usage == null ? "N/D" : `${stats.gpu_usage.toFixed(0)}%${stats.gpu_vram_used_mb != null && stats.gpu_vram_total_mb != null ? ` · ${(stats.gpu_vram_used_mb / 1024).toFixed(1)}/${(stats.gpu_vram_total_mb / 1024).toFixed(0)} GB` : ""}` },
  ];
  return <section className="grid grid-cols-1 border-y border-edge sm:grid-cols-2 lg:grid-cols-4">{items.map((item) => <div key={item.label} className="flex items-center justify-between gap-3 border-edge px-0 py-3 sm:border-r sm:px-4 first:sm:pl-0 last:border-r-0"><span className="flex items-center gap-2 text-xs uppercase tracking-widest text-ink-muted">{item.icon}{item.label}</span><span className="text-xs font-medium tabular-nums text-ink">{item.value}</span></div>)}</section>;
}
