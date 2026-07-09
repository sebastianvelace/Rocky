use serde::Serialize;
use sysinfo::{ProcessesToUpdate, System};

/// Nombre del evento Tauri hacia el frontend. Debe coincidir exactamente con el `listen(...)` en Next.
pub const SYSTEM_STATS_EVENT: &str = "system-stats";

/// Procesos que viajan en cada ranking de cada tick.
pub const TOP_PROCESS_COUNT: usize = 5;

#[derive(Debug, Clone, Default, Serialize)]
pub struct SystemStats {
    pub cpu: f32,
    pub ram: f32,
    pub top_cpu: Vec<ProcessStats>,
    pub top_ram: Vec<ProcessStats>,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct ProcessStats {
    pub pid: String,
    pub name: String,
    pub cpu: f32,
    pub ram: f32,
    pub memory_mb: f32,
    pub protected: bool,
    pub protection_reason: Option<String>,
}

pub fn collect_stats(system: &mut System, protected_pids: &[u32]) -> SystemStats {
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
            let raw_pid = pid.as_u32();
            let memory = process.memory();
            let ram = if total_memory == 0 {
                0.0
            } else {
                ((memory as f64 / total_memory as f64) * 100.0) as f32
            }
            .clamp(0.0, 100.0);
            let name = process.name().to_string_lossy().into_owned();
            let protection_reason = classify_process_protection(raw_pid, &name, protected_pids);

            ProcessStats {
                pid: raw_pid.to_string(),
                name,
                cpu: (process.cpu_usage() / num_cpus).clamp(0.0, 100.0),
                ram,
                memory_mb: (memory as f32 / 1_048_576.0).max(0.0),
                protected: protection_reason.is_some(),
                protection_reason,
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

pub fn classify_process_protection(pid: u32, name: &str, protected_pids: &[u32]) -> Option<String> {
    if pid <= 1 {
        return Some("proceso crítico del sistema".to_string());
    }
    if protected_pids.contains(&pid) {
        return Some("proceso interno de Rocky".to_string());
    }

    let normalized = name.to_ascii_lowercase();
    let protected_name = matches!(
        normalized.as_str(),
        "rocky-ui"
            | "uvicorn"
            | "python"
            | "python3"
            | "xorg"
            | "gnome-shell"
            | "kwin_x11"
            | "kwin_wayland"
            | "plasmashell"
            | "systemd"
            | "dbus-daemon"
            | "pipewire"
            | "wireplumber"
            | "pulseaudio"
            | "webkitwebprocess"
    );
    if protected_name {
        return Some("proceso protegido por Rocky".to_string());
    }

    None
}

#[cfg(test)]
mod tests {
    use super::classify_process_protection;

    #[test]
    fn protects_system_and_rocky_processes() {
        assert!(classify_process_protection(1, "systemd", &[]).is_some());
        assert!(classify_process_protection(42, "node", &[42]).is_some());
        assert!(classify_process_protection(99, "gnome-shell", &[]).is_some());
    }

    #[test]
    fn leaves_regular_user_processes_actionable() {
        assert!(classify_process_protection(1234, "firefox", &[]).is_none());
    }
}
