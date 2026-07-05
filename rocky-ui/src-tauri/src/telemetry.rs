use std::collections::HashMap;

use serde::Serialize;
use sysinfo::{ProcessesToUpdate, System};

/// Nombre del evento Tauri hacia el frontend. Debe coincidir exactamente con el `listen(...)` en Next.
pub const SYSTEM_STATS_EVENT: &str = "system-stats";

/// Procesos que viajan en cada tick (agregados por nombre).
pub const TOP_PROCESS_COUNT: usize = 6;

#[derive(Debug, Clone, Serialize)]
pub struct ProcessStat {
    pub name: String,
    /// % del total de CPU (normalizado por número de núcleos, 0-100).
    pub cpu: f32,
    pub mem_mb: f32,
}

#[derive(Debug, Clone, Serialize)]
pub struct SystemStats {
    pub cpu: f32,
    pub ram: f32,
    pub top: Vec<ProcessStat>,
}

pub fn collect_stats(system: &mut System) -> SystemStats {
    // Un solo “paso” de refresco por ciclo: CPU (lista + métricas), memoria
    // y procesos. `System::new()` arranca sin CPUs cargadas;
    // `refresh_cpu_usage()` solo no basta.
    system.refresh_cpu_all();
    system.refresh_memory();
    system.refresh_processes(ProcessesToUpdate::All, true);

    let cpu = system.global_cpu_usage().clamp(0.0, 100.0);
    let total_memory = system.total_memory();
    let used_memory = system.used_memory();

    let ram = if total_memory == 0 {
        0.0
    } else {
        ((used_memory as f64 / total_memory as f64) * 100.0) as f32
    }
    .clamp(0.0, 100.0);

    SystemStats {
        cpu,
        ram,
        top: top_processes(system),
    }
}

/// Top de procesos agregado por nombre (chrome son 20 procesos; al usuario
/// le importa cuánto come "chrome", no cada PID). CPU normalizada al total
/// de núcleos para que sea comparable con el medidor global.
fn top_processes(system: &System) -> Vec<ProcessStat> {
    let num_cpus = system.cpus().len().max(1) as f32;

    let mut by_name: HashMap<String, (f32, u64)> = HashMap::new();
    for process in system.processes().values() {
        let name = process.name().to_string_lossy().into_owned();
        let entry = by_name.entry(name).or_insert((0.0, 0));
        entry.0 += process.cpu_usage();
        entry.1 += process.memory();
    }

    let mut top: Vec<ProcessStat> = by_name
        .into_iter()
        .map(|(name, (cpu_raw, mem_bytes))| ProcessStat {
            name,
            cpu: (cpu_raw / num_cpus).clamp(0.0, 100.0),
            mem_mb: mem_bytes as f32 / 1_048_576.0,
        })
        .collect();

    top.sort_by(|a, b| {
        b.cpu
            .total_cmp(&a.cpu)
            .then(b.mem_mb.total_cmp(&a.mem_mb))
    });
    top.truncate(TOP_PROCESS_COUNT);
    top
}
