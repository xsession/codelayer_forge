//! Stable data contracts shared by the CodeLayer Forge host, CLI and plugins.

use semver::{Version, VersionReq};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::path::Path;
use thiserror::Error;

pub const PLATFORM_API_VERSION: &str = "0.1.0";

#[derive(Debug, Error)]
pub enum ProtocolError {
    #[error("failed to read manifest: {0}")]
    Io(#[from] std::io::Error),
    #[error("invalid TOML manifest: {0}")]
    Toml(#[from] toml::de::Error),
    #[error("invalid plugin version: {0}")]
    InvalidVersion(#[from] semver::Error),
    #[error("unsupported manifest version {0}; expected 1")]
    UnsupportedManifestVersion(u32),
    #[error("plugin id must be reverse-DNS style: {0}")]
    InvalidPluginId(String),
    #[error("entrypoint is required for runtime {0}")]
    MissingEntrypoint(String),
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum PluginRuntime {
    Python,
    Native,
    Wasm,
    Webview,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PluginPermissions {
    #[serde(default)]
    pub workspace_read: bool,
    #[serde(default)]
    pub workspace_write: bool,
    #[serde(default)]
    pub network: bool,
    #[serde(default)]
    pub serial: bool,
    #[serde(default)]
    pub usb: bool,
    #[serde(default)]
    pub spawn_processes: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CapabilityMap(pub BTreeMap<String, String>);

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Contributions {
    #[serde(default)]
    pub workbenches: Vec<WorkbenchContribution>,
    #[serde(default)]
    pub commands: Vec<CommandContribution>,
    #[serde(default)]
    pub views: Vec<ViewContribution>,
    #[serde(default)]
    pub editors: Vec<EditorContribution>,
    #[serde(default)]
    pub settings: Vec<SettingContribution>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkbenchContribution {
    pub id: String,
    pub title: String,
    #[serde(default)]
    pub icon: Option<String>,
    #[serde(default)]
    pub order: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandContribution {
    pub id: String,
    pub title: String,
    #[serde(default)]
    pub category: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ViewContribution {
    pub id: String,
    pub title: String,
    pub location: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EditorContribution {
    pub id: String,
    pub label: String,
    #[serde(default)]
    pub extensions: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettingContribution {
    pub key: String,
    pub title: String,
    #[serde(rename = "type")]
    pub kind: String,
    #[serde(default)]
    pub default: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginManifest {
    pub manifest_version: u32,
    pub id: String,
    pub name: String,
    pub version: String,
    pub publisher: String,
    pub description: String,
    pub runtime: PluginRuntime,
    #[serde(default)]
    pub entrypoint: Option<String>,
    pub platform_api: String,
    #[serde(default)]
    pub activation_events: Vec<String>,
    #[serde(default)]
    pub supported_os: Vec<String>,
    #[serde(default)]
    pub contributes: Contributions,
    #[serde(default)]
    pub provides: BTreeMap<String, String>,
    #[serde(default)]
    pub requires: BTreeMap<String, String>,
    #[serde(default)]
    pub permissions: PluginPermissions,
}

impl PluginManifest {
    pub fn from_path(path: impl AsRef<Path>) -> Result<Self, ProtocolError> {
        let text = std::fs::read_to_string(path)?;
        let manifest: Self = toml::from_str(&text)?;
        manifest.validate()?;
        Ok(manifest)
    }

    pub fn validate(&self) -> Result<(), ProtocolError> {
        if self.manifest_version != 1 {
            return Err(ProtocolError::UnsupportedManifestVersion(self.manifest_version));
        }
        let segments: Vec<_> = self.id.split('.').collect();
        if segments.len() < 3
            || segments.iter().any(|part| {
                part.is_empty()
                    || !part
                        .chars()
                        .all(|c| c.is_ascii_alphanumeric() || c == '-')
            })
        {
            return Err(ProtocolError::InvalidPluginId(self.id.clone()));
        }
        Version::parse(&self.version)?;
        VersionReq::parse(&self.platform_api)?;
        if matches!(self.runtime, PluginRuntime::Python | PluginRuntime::Native)
            && self.entrypoint.as_deref().unwrap_or_default().is_empty()
        {
            return Err(ProtocolError::MissingEntrypoint(format!("{:?}", self.runtime)));
        }
        Ok(())
    }

    pub fn supports_platform(&self, platform_version: &Version) -> Result<bool, ProtocolError> {
        Ok(VersionReq::parse(&self.platform_api)?.matches(platform_version))
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: Option<Value>,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcErrorObject {
    pub code: i64,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub id: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcErrorObject>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_a_manifest() {
        let manifest: PluginManifest = toml::from_str(
            r#"
manifest_version = 1
id = "hu.codelayer.example"
name = "Example"
version = "1.2.3"
publisher = "CodeLayer"
description = "Example plugin"
runtime = "python"
entrypoint = "example.plugin:create_plugin"
platform_api = ">=0.1,<0.2"
"#,
        )
        .expect("parse manifest");
        manifest.validate().expect("valid manifest");
    }
}
