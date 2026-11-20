use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeInfo {
    pub status: String,
    pub api_origin: Option<String>,
    pub api_token: Option<String>,
    pub error: Option<String>,
    pub log_path: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Handshake {
    api_origin: String,
    api_token: String,
}

pub struct Runtime {
    data_dir: PathBuf,
    child: Mutex<Option<Child>>,
    info: Mutex<RuntimeInfo>,
    generation: AtomicU64,
}

impl Runtime {
    pub fn new(data_dir: PathBuf) -> Arc<Self> {
        Arc::new(Self {
            info: Mutex::new(RuntimeInfo {
                status: "starting".into(),
                api_origin: None,
                api_token: None,
                error: None,
                log_path: data_dir.join("logs/api.log").to_string_lossy().into(),
            }),
            data_dir,
            child: Mutex::new(None),
            generation: AtomicU64::new(0),
        })
    }

    pub fn info(&self) -> RuntimeInfo {
        let mut info = self.info.lock().unwrap().clone();
        if info.status == "ready" {
            let mut child = self.child.lock().unwrap();
            if child
                .as_mut()
                .is_none_or(|process| !matches!(process.try_wait(), Ok(None)))
            {
                info.status = "failed".into();
                info.api_token = None;
                info.error = Some("The local service stopped. Retry to restart it.".into());
            }
        }
        info
    }

    pub fn start(self: &Arc<Self>) {
        let generation = self.generation.fetch_add(1, Ordering::SeqCst) + 1;
        {
            let mut info = self.info.lock().unwrap();
            info.status = "starting".into();
            info.error = None;
            info.api_origin = None;
            info.api_token = None;
        }
        let runtime = Arc::clone(self);
        std::thread::spawn(move || {
            let result = runtime.launch();
            if runtime.generation.load(Ordering::SeqCst) != generation {
                return;
            }
            let mut info = runtime.info.lock().unwrap();
            match result {
                Ok(handshake) => {
                    info.status = "ready".into();
                    info.api_origin = Some(handshake.api_origin);
                    info.api_token = Some(handshake.api_token);
                }
                Err(error) => {
                    info.status = "failed".into();
                    info.error = Some(format!("Could not start the local service: {error}"));
                    drop(info);
                    runtime.stop_child();
                }
            }
        });
    }

    fn launch(&self) -> Result<Handshake, String> {
        let run = || -> Result<Handshake, Box<dyn std::error::Error>> {
            let logs = self.data_dir.join("logs");
            fs::create_dir_all(&logs)?;
            let log = OpenOptions::new()
                .create(true)
                .append(true)
                .open(logs.join("api.log"))?;
            let name = if cfg!(windows) {
                "novelforge-api.exe"
            } else {
                "novelforge-api"
            };
            let executable = std::env::current_exe()?;
            let sidecar = executable
                .parent()
                .ok_or("No application directory")?
                .join(name);
            let mut command = Command::new(sidecar);
            #[cfg(unix)]
            {
                use std::os::unix::process::CommandExt;
                command.process_group(0);
            }
            command
                .arg("--data-dir")
                .arg(&self.data_dir)
                .arg("--watch-stdin")
                .current_dir(&self.data_dir)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(log);
            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                command.creation_flags(0x08000000);
            }
            let mut child = command.spawn()?;
            let stdout = child.stdout.take().ok_or("No service handshake pipe")?;
            *self.child.lock().unwrap() = Some(child);
            let (sender, receiver) = mpsc::channel();
            std::thread::spawn(move || {
                let mut line = String::new();
                let result = BufReader::new(stdout).take(16_384).read_line(&mut line);
                let _ = sender.send(result.map(|_| line));
            });
            let line = receiver.recv_timeout(Duration::from_secs(45))??;
            let handshake: Handshake = serde_json::from_str(&line)?;
            let address: SocketAddr = handshake
                .api_origin
                .strip_prefix("http://")
                .ok_or("Invalid local service origin")?
                .parse()?;
            if !address.ip().is_loopback() || handshake.api_token.len() < 32 {
                return Err("Invalid local service handshake".into());
            }
            let deadline = Instant::now() + Duration::from_secs(5);
            loop {
                if is_ready(address, &handshake.api_token) {
                    return Ok(handshake);
                }
                if Instant::now() >= deadline {
                    return Err("The local service did not become ready; inspect api.log".into());
                }
                std::thread::sleep(Duration::from_millis(100));
            }
        };
        run().map_err(|error| error.to_string())
    }

    fn stop_child(&self) {
        if let Some(mut child) = self.child.lock().unwrap().take() {
            // EOF lets the Python server shut down, including PyInstaller's child.
            drop(child.stdin.take());
            let deadline = Instant::now() + Duration::from_secs(4);
            while matches!(child.try_wait(), Ok(None)) && Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(50));
            }
            if matches!(child.try_wait(), Ok(None)) {
                #[cfg(unix)]
                {
                    // Only this sidecar's dedicated process group is affected.
                    unsafe {
                        libc::killpg(child.id() as libc::pid_t, libc::SIGKILL);
                    }
                }
                #[cfg(windows)]
                {
                    use std::os::windows::process::CommandExt;
                    if let Some(root) = std::env::var_os("SystemRoot") {
                        let _ = Command::new(PathBuf::from(root).join("System32/taskkill.exe"))
                            .args(["/PID", &child.id().to_string(), "/T", "/F"])
                            .creation_flags(0x08000000)
                            .status();
                    }
                }
                let _ = child.kill();
            }
            let _ = child.wait();
        }
    }

    pub fn stop(&self) {
        self.generation.fetch_add(1, Ordering::SeqCst);
        self.stop_child();
    }
}

fn is_ready(address: SocketAddr, token: &str) -> bool {
    let check = || -> std::io::Result<bool> {
        let mut stream = TcpStream::connect_timeout(&address, Duration::from_millis(300))?;
        stream.set_read_timeout(Some(Duration::from_millis(500)))?;
        stream.set_write_timeout(Some(Duration::from_millis(500)))?;
        write!(stream, "GET /ready HTTP/1.1\r\nHost: {address}\r\nX-NovelForge-Local-Token: {token}\r\nConnection: close\r\n\r\n")?;
        let mut status = String::new();
        BufReader::new(stream).read_line(&mut status)?;
        Ok(status.starts_with("HTTP/1.1 200 "))
    };
    check().unwrap_or(false)
}
