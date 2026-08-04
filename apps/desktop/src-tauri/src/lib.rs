use forge_core::PluginRegistry;
use serde::Serialize;
use serde_json::{Value, json};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct PlatformInfo {
    name: &'static str,
    version: &'static str,
    platform_api: &'static str,
    os: &'static str,
    arch: &'static str,
}

#[tauri::command]
fn get_platform_info() -> PlatformInfo {
    PlatformInfo {
        name: "CodeLayer Forge",
        version: env!("CARGO_PKG_VERSION"),
        platform_api: forge_protocol::PLATFORM_API_VERSION,
        os: std::env::consts::OS,
        arch: std::env::consts::ARCH,
    }
}

#[tauri::command]
fn discover_plugins(plugins_root: Option<String>) -> Result<Value, String> {
    let root = plugins_root
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("plugins"));
    let registry = PluginRegistry::discover(&root).map_err(|error| error.to_string())?;
    let plugins: Vec<_> = registry.plugins().collect();
    serde_json::to_value(plugins).map_err(|error| error.to_string())
}

#[tauri::command]
async fn run_plugin_command(
    plugin_id: String,
    command: String,
    arguments: Value,
    plugins_root: Option<String>,
    workspace_root: Option<String>,
) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let plugins_root = plugins_root
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("plugins"));
        let workspace_root = workspace_root
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("examples/demo-workspace"));
        run_python_plugin(&plugins_root, &workspace_root, &plugin_id, &command, arguments)
    })
    .await
    .map_err(|error| error.to_string())?
}

fn run_python_plugin(
    plugins_root: &Path,
    workspace_root: &Path,
    plugin_id: &str,
    command: &str,
    arguments: Value,
) -> Result<Value, String> {
    let registry = PluginRegistry::discover(plugins_root).map_err(|error| error.to_string())?;
    let plugin = registry
        .get(plugin_id)
        .ok_or_else(|| format!("plugin not found: {plugin_id}"))?;
    let repo_root = plugins_root
        .parent()
        .unwrap_or_else(|| Path::new("."));
    let host = repo_root.join("hosts/python-plugin-host/forge_plugin_host.py");
    if !host.is_file() {
        return Err(format!("Python plugin host not found: {}", host.display()));
    }
    let python = std::env::var("FORGE_PYTHON").unwrap_or_else(|_| {
        if cfg!(target_os = "windows") { "python".into() } else { "python3".into() }
    });
    let mut child = Command::new(python)
        .arg(host)
        .arg("--plugin-dir")
        .arg(&plugin.root)
        .arg("--workspace")
        .arg(workspace_root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|error| format!("failed to start plugin host: {error}"))?;
    let mut stdin = child.stdin.take().ok_or("failed to open plugin stdin")?;
    let stdout = child.stdout.take().ok_or("failed to open plugin stdout")?;
    let mut reader = BufReader::new(stdout);

    let requests = [
        json!({"jsonrpc":"2.0","id":1,"method":"forge/initialize","params":{}}),
        json!({
            "jsonrpc":"2.0",
            "id":2,
            "method":"forge/executeCommand",
            "params":{"command":command,"arguments":arguments}
        }),
        json!({"jsonrpc":"2.0","id":3,"method":"forge/shutdown","params":{}}),
    ];
    let mut command_response = None;
    for request in requests {
        writeln!(stdin, "{request}").map_err(|error| error.to_string())?;
        stdin.flush().map_err(|error| error.to_string())?;
        let mut line = String::new();
        reader.read_line(&mut line).map_err(|error| error.to_string())?;
        if request["id"].as_i64() == Some(2) {
            command_response = Some(
                serde_json::from_str::<Value>(line.trim()).map_err(|error| error.to_string())?,
            );
        }
    }
    drop(stdin);
    let status = child.wait().map_err(|error| error.to_string())?;
    if !status.success() {
        return Err(format!("plugin host exited with {status}"));
    }
    command_response.ok_or_else(|| "plugin host returned no command response".into())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_platform_info,
            discover_plugins,
            run_plugin_command
        ])
        .run(tauri::generate_context!())
        .expect("error while running CodeLayer Forge");
}
