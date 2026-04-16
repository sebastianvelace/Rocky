use serde::Serialize;
use sysinfo::System;

/// Nombre del evento Tauri hacia el frontend. Debe coincidir exactamente con el `listen(...)` en Next.
pub const SYSTEM_STATS_EVENT: &str = "system-stats";

#[derive(Debug, Clone, Serialize)]
pub struct SystemStats {
    pub cpu: f32,
    pub ram: f32,
}

pub fn collect_stats(system: &mut System) -> SystemStats {
    // Un solo “paso” de refresco por ciclo: CPU (lista + métricas) y memoria.
    // `System::new()` arranca sin CPUs cargadas; `refresh_cpu_usage()` solo no basta.
    system.refresh_cpu_all();
    system.refresh_memory();

    let cpu = system.global_cpu_usage().clamp(0.0, 100.0);
    let total_memory = system.total_memory();
    let used_memory = system.used_memory();

    let ram = if total_memory == 0 {
        0.0
    } else {
        ((used_memory as f64 / total_memory as f64) * 100.0) as f32
    }
    .clamp(0.0, 100.0);

    SystemStats { cpu, ram }
}
