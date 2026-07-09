use std::fs;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use serde::Serialize;
use sysinfo::{Components, Disks, Networks, ProcessesToUpdate, System};

/// Nombre del evento Tauri hacia el frontend. Debe coincidir exactamente con el `listen(...)` en Next.
pub const SYSTEM_STATS_EVENT: &str = "system-stats";

/// Procesos que viajan en cada ranking de cada tick.
pub const TOP_PROCESS_COUNT: usize = 5;

#[derive(Debug, Clone, Default, Serialize)]
pub struct SystemStats {
    pub cpu: f32,
    pub ram: f32,
    pub disk_used: f32,
    pub network_rx_kbps: f32,
    pub network_tx_kbps: f32,
    pub temperature_c: Option<f32>,
    pub gpu_usage: Option<f32>,
    pub gpu_vram_used_mb: Option<f32>,
    pub gpu_vram_total_mb: Option<f32>,
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

#[derive(Debug, Clone, Copy)]
struct GpuStats {
    usage: Option<f32>,
    vram_used_mb: Option<f32>,
    vram_total_mb: Option<f32>,
}

/// Lee sysfs cada dos segundos: no crea procesos ni depende de una GPU concreta.
pub struct GpuProbe {
    root: PathBuf,
    last: Option<GpuStats>,
    last_refresh: Option<Instant>,
}

impl GpuProbe {
    pub fn new() -> Self {
        Self::from_root(PathBuf::from("/sys/class/drm"))
    }

    fn from_root(root: PathBuf) -> Self {
        Self {
            root,
            last: None,
            last_refresh: None,
        }
    }

    fn sample(&mut self) -> Option<GpuStats> {
        if self
            .last_refresh
            .is_some_and(|instant| instant.elapsed() < Duration::from_secs(2))
        {
            return self.last;
        }
        self.last_refresh = Some(Instant::now());
        self.last = fs::read_dir(&self.root)
            .ok()?
            .filter_map(Result::ok)
            .filter(|entry| entry.file_name().to_string_lossy().starts_with("card"))
            .filter_map(|entry| read_gpu_stats(&entry.path().join("device")))
            .next();
        self.last
    }
}

fn read_number<T: std::str::FromStr>(path: &Path) -> Option<T> {
    fs::read_to_string(path).ok()?.trim().parse::<T>().ok()
}

fn read_gpu_stats(device: &Path) -> Option<GpuStats> {
    let usage =
        read_number::<f32>(&device.join("gpu_busy_percent")).map(|value| value.clamp(0.0, 100.0));
    let used = read_number::<u64>(&device.join("mem_info_vram_used"));
    let total = read_number::<u64>(&device.join("mem_info_vram_total"));
    if usage.is_none() && used.is_none() && total.is_none() {
        return None;
    }
    Some(GpuStats {
        usage,
        vram_used_mb: used.map(|value| value as f32 / 1_048_576.0),
        vram_total_mb: total.map(|value| value as f32 / 1_048_576.0),
    })
}

pub fn collect_stats(
    system: &mut System,
    disks: &mut Disks,
    networks: &mut Networks,
    components: &mut Components,
    gpu: &mut GpuProbe,
    protected_pids: &[u32],
) -> SystemStats {
    // Un solo “paso” de refresco por ciclo: CPU (lista + métricas), memoria
    // y procesos. `System::new()` arranca sin CPUs cargadas;
    // `refresh_cpu_usage()` solo no basta.
    system.refresh_cpu_all();
    system.refresh_memory();
    system.refresh_processes(ProcessesToUpdate::All, true);
    disks.refresh(false);
    networks.refresh(false);
    components.refresh(false);

    let cpu = system.global_cpu_usage().clamp(0.0, 100.0);
    let total_memory = system.total_memory();
    let used_memory = system.used_memory();

    let ram = if total_memory == 0 {
        0.0
    } else {
        ((used_memory as f64 / total_memory as f64) * 100.0) as f32
    }
    .clamp(0.0, 100.0);

    let (total_disk, available_disk) = disks.iter().fold((0_u64, 0_u64), |acc, disk| {
        (
            acc.0.saturating_add(disk.total_space()),
            acc.1.saturating_add(disk.available_space()),
        )
    });
    let disk_used = if total_disk == 0 {
        0.0
    } else {
        (100.0 - (available_disk as f64 / total_disk as f64) * 100.0) as f32
    }
    .clamp(0.0, 100.0);

    let (received, transmitted) = networks.values().fold((0_u64, 0_u64), |acc, network| {
        (
            acc.0.saturating_add(network.received()),
            acc.1.saturating_add(network.transmitted()),
        )
    });
    let temperature_c = components
        .iter()
        .filter_map(|component| component.temperature())
        .filter(|temperature| temperature.is_finite())
        .max_by(|a, b| a.total_cmp(b));
    let gpu_stats = gpu.sample();

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
        disk_used,
        network_rx_kbps: received as f32 / 1024.0,
        network_tx_kbps: transmitted as f32 / 1024.0,
        temperature_c,
        gpu_usage: gpu_stats.and_then(|stats| stats.usage),
        gpu_vram_used_mb: gpu_stats.and_then(|stats| stats.vram_used_mb),
        gpu_vram_total_mb: gpu_stats.and_then(|stats| stats.vram_total_mb),
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
    use super::{classify_process_protection, GpuProbe};
    use std::fs;

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

    #[test]
    fn reads_gpu_metrics_when_driver_publishes_sysfs_files() {
        let root = std::env::temp_dir().join(format!("rocky-gpu-test-{}", std::process::id()));
        let device = root.join("card0/device");
        fs::create_dir_all(&device).unwrap();
        fs::write(device.join("gpu_busy_percent"), "72\n").unwrap();
        fs::write(device.join("mem_info_vram_used"), "104857600\n").unwrap();
        fs::write(device.join("mem_info_vram_total"), "209715200\n").unwrap();

        let mut probe = GpuProbe::from_root(root.clone());
        let stats = probe.sample().unwrap();
        assert_eq!(stats.usage, Some(72.0));
        assert_eq!(stats.vram_used_mb, Some(100.0));
        assert_eq!(stats.vram_total_mb, Some(200.0));
        fs::remove_dir_all(root).unwrap();
    }
}
