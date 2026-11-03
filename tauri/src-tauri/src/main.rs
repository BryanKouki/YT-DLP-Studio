//! Casca nativa do YT-DLP Studio. Toda a lógica do app fica no TypeScript (src/backend.ts);
//! aqui só existe o que a página não consegue fazer sozinha: processos, arquivos, download e diálogos.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Read, Write};
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use tauri::webview::PageLoadEvent;
use tauri::{AppHandle, Emitter, Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder, WindowEvent};

const CREATE_NO_WINDOW: u32 = 0x0800_0000; // sem janela de console piscando

/// id escolhido pela página -> PID do processo em execução
#[derive(Default)]
struct Procs(Mutex<HashMap<u32, u32>>);

/// Pasta de dados portátil: 'data' ao lado do .exe (nunca a pasta temporária de build).
/// Se não der pra escrever ali (ex.: Arquivos de Programas), cai para %APPDATA%\YT-DLP Studio.
fn data_dir() -> PathBuf {
    let portable = std::env::current_exe().ok().and_then(|exe| Some(exe.parent()?.join("data")));
    if let Some(dir) = portable {
        let probe = dir.join(".write_test");
        if std::fs::create_dir_all(&dir).is_ok() && std::fs::write(&probe, "ok").is_ok() {
            let _ = std::fs::remove_file(probe);
            return dir;
        }
    }
    let dir = PathBuf::from(std::env::var("APPDATA").unwrap_or_default()).join("YT-DLP Studio");
    let _ = std::fs::create_dir_all(&dir);
    dir
}

fn taskkill(pid: u32) {
    // /T mata a árvore inteira: o yt-dlp.exe tem um processo filho e ainda chama o ffmpeg
    let _ = Command::new("taskkill")
        .args(["/pid", &pid.to_string(), "/T", "/F"])
        .creation_flags(CREATE_NO_WINDOW)
        .spawn();
}

/// Inicia um processo e entrega a saída linha a linha: evento "proc" (id, linha, é_stderr)
/// e, no fim, "exit" (id, código). As leituras rodam em threads; a página só recebe eventos.
#[tauri::command]
fn spawn(app: AppHandle, procs: State<Procs>, id: u32, exe: String, args: Vec<String>) -> Result<(), String> {
    let mut child = Command::new(&exe)
        .args(&args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .map_err(|e| e.to_string())?;
    procs.0.lock().unwrap().insert(id, child.id());

    let streams: [(Box<dyn Read + Send>, bool); 2] = [
        (Box::new(child.stdout.take().unwrap()), false),
        (Box::new(child.stderr.take().unwrap()), true),
    ];
    let readers: Vec<_> = streams
        .into_iter()
        .map(|(stream, is_err)| {
            let app = app.clone();
            std::thread::spawn(move || {
                let mut reader = BufReader::new(stream);
                let mut buf = Vec::new();
                while reader.read_until(b'\n', &mut buf).unwrap_or(0) > 0 {
                    let line = String::from_utf8_lossy(&buf);
                    let line = line.trim_end();
                    if !line.trim().is_empty() {
                        let _ = app.emit("proc", (id, line, is_err));
                    }
                    buf.clear();
                }
            })
        })
        .collect();

    std::thread::spawn(move || {
        for reader in readers {
            let _ = reader.join(); // todas as linhas saem antes do "exit"
        }
        let code = child.wait().ok().and_then(|status| status.code()).unwrap_or(-1);
        app.state::<Procs>().0.lock().unwrap().remove(&id);
        let _ = app.emit("exit", (id, code));
    });
    Ok(())
}

#[tauri::command]
fn kill(procs: State<Procs>, id: u32) {
    if let Some(pid) = procs.0.lock().unwrap().get(&id) {
        taskkill(*pid);
    }
}

/// Baixa url para dest (via dest.part), emitindo "dl" (id, porcentagem ou -1 se o tamanho é desconhecido).
#[tauri::command]
async fn download(app: AppHandle, id: u32, url: String, dest: String) -> Result<(), String> {
    let job = move || -> Result<(), Box<dyn std::error::Error>> {
        let resp = ureq::get(&url).set("User-Agent", "YT-DLP-Studio/1.0").call()?;
        let total: u64 = resp.header("Content-Length").and_then(|v| v.parse().ok()).unwrap_or(0);
        let tmp = format!("{dest}.part");
        let mut file = std::fs::File::create(&tmp)?;
        let mut reader = resp.into_reader();
        let mut buf = vec![0u8; 256 * 1024];
        let (mut done, mut last) = (0u64, -2i64);
        loop {
            let n = reader.read(&mut buf)?;
            if n == 0 {
                break;
            }
            file.write_all(&buf[..n])?;
            done += n as u64;
            let pct = if total > 0 { (done * 100 / total) as i64 } else { -1 };
            if pct != last {
                last = pct;
                let _ = app.emit("dl", (id, pct));
            }
        }
        drop(file);
        std::fs::rename(&tmp, &dest)?;
        Ok(())
    };
    tauri::async_runtime::spawn_blocking(move || job().map_err(|e| e.to_string()))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
fn write_text(path: String, text: String) -> bool {
    std::fs::write(path, text).is_ok()
}

#[tauri::command]
fn mkdir(path: String) -> bool {
    std::fs::create_dir_all(path).is_ok()
}

#[tauri::command]
fn is_file(path: String) -> bool {
    std::path::Path::new(&path).is_file()
}

#[tauri::command]
fn remove(path: String) {
    let _ = std::fs::remove_file(path);
}

#[tauri::command]
fn copy(from: String, to: String) -> bool {
    std::fs::copy(from, to).is_ok()
}

/// Arquivos de uma pasta: (nome, data de modificação em ms).
#[tauri::command]
fn list_dir(path: String) -> Vec<(String, f64)> {
    let Ok(entries) = std::fs::read_dir(path) else { return Vec::new() };
    entries
        .flatten()
        .filter(|entry| entry.path().is_file())
        .map(|entry| {
            let mtime = entry.metadata().and_then(|m| m.modified()).ok();
            let ms = mtime.and_then(|t| t.duration_since(UNIX_EPOCH).ok()).map_or(0.0, |d| d.as_millis() as f64);
            (entry.file_name().to_string_lossy().into_owned(), ms)
        })
        .collect()
}

fn ms(time: std::io::Result<SystemTime>) -> f64 {
    time.ok().and_then(|t| t.duration_since(UNIX_EPOCH).ok()).map_or(0.0, |d| d.as_millis() as f64)
}

/// (criação, modificação) em ms.
#[tauri::command]
fn file_times(path: String) -> Option<(f64, f64)> {
    let meta = std::fs::metadata(path).ok()?;
    Some((ms(meta.created()), ms(meta.modified())))
}

/// Grava as datas de criação e modificação (ms): encaixa a faixa substituta na ordem da playlist.
#[tauri::command]
fn set_times(path: String, created: f64, modified: f64) -> bool {
    use std::os::windows::fs::FileTimesExt;
    let at = |ms: f64| UNIX_EPOCH + Duration::from_millis(ms as u64);
    let times = std::fs::FileTimes::new().set_created(at(created)).set_modified(at(modified));
    std::fs::OpenOptions::new().write(true).open(path).and_then(|file| file.set_times(times)).is_ok()
}

#[tauri::command]
fn quit(app: AppHandle) {
    app.exit(0); // RunEvent::Exit mata os downloads em andamento
}

#[tauri::command]
fn open_path(path: String) {
    let _ = Command::new("explorer").arg(path).spawn();
}

// async: o diálogo bloqueia, então não pode rodar na thread principal
#[tauri::command]
async fn pick(window: tauri::WebviewWindow, folder: bool, initial: Option<String>) -> Option<String> {
    let mut dialog = rfd::FileDialog::new().set_parent(&window);
    if let Some(dir) = initial.filter(|dir| std::path::Path::new(dir).is_dir()) {
        dialog = dialog.set_directory(dir);
    }
    let chosen = if folder { dialog.pick_folder() } else { dialog.pick_file() };
    chosen.map(|path| path.to_string_lossy().into_owned())
}

fn main() {
    let dir = data_dir();
    let settings = std::fs::read_to_string(dir.join("settings.json")).unwrap_or_default();
    let saved: serde_json::Value = serde_json::from_str(&settings).unwrap_or_default();
    let size = |i: usize, default: f64| saved["window_size"][i].as_f64().unwrap_or(default);
    let (width, height) = (size(0, 840.0), size(1, 820.0));

    // Tudo que a página precisa pra desenhar a primeira tela já vai pronto (sem ida e volta assíncrona).
    let init = serde_json::json!({
        "dir": dir,
        "home": std::env::var("USERPROFILE").unwrap_or_default(),
        "tar": PathBuf::from(std::env::var("SystemRoot").unwrap_or_else(|_| "C:\\Windows".into()))
            .join("System32").join("tar.exe"),
        "settings": saved,
    });

    tauri::Builder::default()
        .manage(Procs::default())
        .invoke_handler(tauri::generate_handler![
            spawn, kill, download, write_text, mkdir, is_file, remove, copy, list_dir, file_times, set_times, open_path, pick, quit
        ])
        .on_page_load(|webview, payload| {
            if payload.event() == PageLoadEvent::Finished {
                let _ = webview.window().show(); // só aparece já desenhada (sem clarão branco)
            }
        })
        .setup(move |app| {
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::default())
                .title("YT-DLP Studio")
                .inner_size(width, height)
                .min_inner_size(720.0, 620.0)
                .visible(false)
                .data_directory(dir.join("webview")) // cache do WebView2 também fica em data/
                .initialization_script(&format!("window.__INIT__ = {init};"))
                .build()?;
            // fechar pede confirmação na interface; o comando quit fecha de verdade
            let handle = window.clone();
            window.on_window_event(move |event| {
                if let WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = handle.emit("close_requested", ());
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("erro ao iniciar o YT-DLP Studio")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                for pid in app.state::<Procs>().0.lock().unwrap().values() {
                    taskkill(*pid);
                }
            }
        });
}
