use serde::Serialize;
use sysinfo::{ProcessesToUpdate, System};

/// Nombre del evento Tauri hacia el frontend. Debe coincidir exactamente con el `listen(...)` en Next.
pub const SYSTEM_STATS_EVENT: &str = "system-stats";

/// Procesos que viajan en cada ranking de cada tick.
pub const TOP_PROCESS_COUNT: usize = 5;

#[derive(Debug, Clone, Serialize)]
pub struct SystemStats {
    pub cpu: f32,
    pub ram: f32,
    pub top_cpu: Vec<ProcessStats>,
    pub top_ram: Vec<ProcessStats>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProcessStats {
    pub pid: String,
    pub name: String,
    pub cpu: f32,
    pub ram: f32,
    pub memory_mb: f32,
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

    let num_cpus = system.cpus().len().max(1) as f32;
    let mut processes: Vec<ProcessStats> = system
        .processes()
        .iter()
        .map(|(pid, process)| {
            let memory = process.memory();
            let ram = if total_memory == 0 {
                0.0
            } else {
                ((memory as f64 / total_memory as f64) * 100.0) as f32
            }
            .clamp(0.0, 100.0);

            ProcessStats {
                pid: pid.to_string(),
                name: process.name().to_string_lossy().into_owned(),
                cpu: (process.cpu_usage() / num_cpus).clamp(0.0, 100.0),
                ram,
                memory_mb: (memory as f32 / 1_048_576.0).max(0.0),
            }
        })
        .filter(|process| process.cpu > 0.1 || process.memory_mb > 1.0)
        .collect();

    let mut top_cpu = processes.clone();
    top_cpu.sort_by(|a, b| b.cpu.total_cmp(&a.cpu));
    top_cpu.truncate(TOP_PROCESS_COUNT);

    processes.sort_by(|a, b| b.memory_mb.total_cmp(&a.memory_mb));
    processes.truncate(TOP_PROCESS_COUNT);

    SystemStats {
        cpu,
        ram,
        top_cpu,
        top_ram: processes,
    }
}
