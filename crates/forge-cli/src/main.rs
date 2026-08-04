use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use forge_core::{PluginRegistry, WorkspaceManifest};
use serde_json::{Value, json};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

#[derive(Debug, Parser)]
#[command(name = "forge", version, about = "CodeLayer Forge command-line client")]
struct Cli {
    #[arg(long, global = true, default_value = "plugins")]
    plugins_root: PathBuf,
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    Plugins {
        #[command(subcommand)]
        command: PluginCommands,
    },
    Workspace {
        #[command(subcommand)]
        command: WorkspaceCommands,
    },
}

#[derive(Debug, Subcommand)]
enum PluginCommands {
    List {
        #[arg(long)]
        json: bool,
    },
    Validate,
    Call {
        plugin_id: String,
        method: String,
        #[arg(long, default_value = "{}")]
        params: String,
        #[arg(long, default_value = "python3")]
        python: String,
        #[arg(long, default_value = "hosts/python-plugin-host/forge_plugin_host.py")]
        host: PathBuf,
    },
}

#[derive(Debug, Subcommand)]
enum WorkspaceCommands {
    Init { path: PathBuf, #[arg(long)] name: Option<String> },
    Validate { path: PathBuf },
}

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .with_writer(std::io::stderr)
        .init();
    let cli = Cli::parse();
    match cli.command {
        Commands::Plugins { command } => plugin_command(&cli.plugins_root, command),
        Commands::Workspace { command } => workspace_command(command),
    }
}

fn plugin_command(root: &Path, command: PluginCommands) -> Result<()> {
    let registry = PluginRegistry::discover(root)
        .with_context(|| format!("discover plugins under {}", root.display()))?;
    match command {
        PluginCommands::List { json: as_json } => {
            if as_json {
                let rows: Vec<_> = registry.plugins().collect();
                println!("{}", serde_json::to_string_pretty(&rows)?);
            } else {
                for plugin in registry.plugins() {
                    println!(
                        "{:<38} {:<10} {}",
                        plugin.manifest.id, plugin.manifest.version, plugin.manifest.name
                    );
                }
            }
            Ok(())
        }
        PluginCommands::Validate => {
            registry.validate_dependencies()?;
            for plugin in registry.plugins() {
                if !plugin.platform_compatible {
                    bail!("plugin {} is incompatible with this platform API", plugin.manifest.id);
                }
            }
            println!("validated {} plugins", registry.plugins().count());
            Ok(())
        }
        PluginCommands::Call {
            plugin_id,
            method,
            params,
            python,
            host,
        } => {
            let plugin = registry
                .get(&plugin_id)
                .with_context(|| format!("plugin not found: {plugin_id}"))?;
            let params: Value = serde_json::from_str(&params).context("parse --params JSON")?;
            call_python_host(&python, &host, &plugin.root, &method, params)
        }
    }
}

fn call_python_host(
    python: &str,
    host: &Path,
    plugin_root: &Path,
    method: &str,
    params: Value,
) -> Result<()> {
    let mut child = Command::new(python)
        .arg(host)
        .arg("--plugin-dir")
        .arg(plugin_root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .context("start Python plugin host")?;

    let mut stdin = child.stdin.take().context("open child stdin")?;
    let stdout = child.stdout.take().context("open child stdout")?;
    let mut reader = BufReader::new(stdout);

    for request in [
        json!({"jsonrpc":"2.0","id":1,"method":"forge/initialize","params":{}}),
        json!({"jsonrpc":"2.0","id":2,"method":method,"params":params}),
        json!({"jsonrpc":"2.0","id":3,"method":"forge/shutdown","params":{}}),
    ] {
        writeln!(stdin, "{}", serde_json::to_string(&request)?)?;
        stdin.flush()?;
        let mut line = String::new();
        reader.read_line(&mut line)?;
        if request["id"].as_i64() == Some(2) {
            let response: Value = serde_json::from_str(line.trim())?;
            println!("{}", serde_json::to_string_pretty(&response)?);
        }
    }
    drop(stdin);
    let status = child.wait()?;
    if !status.success() {
        bail!("plugin host exited with {status}");
    }
    Ok(())
}

fn workspace_command(command: WorkspaceCommands) -> Result<()> {
    match command {
        WorkspaceCommands::Init { path, name } => {
            std::fs::create_dir_all(&path)?;
            for directory in ["devices", "pin-plans", "hdl", "routes", "constraints", ".codelayer/cache", ".codelayer/state"] {
                std::fs::create_dir_all(path.join(directory))?;
            }
            let fallback_name = path
                .file_name()
                .and_then(|name| name.to_str())
                .unwrap_or("Forge Workspace")
                .to_owned();
            let manifest = WorkspaceManifest {
                schema_version: 1,
                id: fallback_name.to_lowercase().replace(' ', "-"),
                name: name.unwrap_or(fallback_name),
                description: String::new(),
                enabled_plugins: Vec::new(),
                settings: json!({}),
            };
            manifest.save(path.join("project.cforge"))?;
            println!("created {}", path.display());
            Ok(())
        }
        WorkspaceCommands::Validate { path } => {
            let manifest = WorkspaceManifest::load(path.join("project.cforge"))?;
            println!("workspace {} ({}) is valid", manifest.name, manifest.id);
            Ok(())
        }
    }
}
