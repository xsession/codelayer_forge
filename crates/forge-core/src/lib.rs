//! Core registry and workspace services. Domain-specific engineering logic belongs in plugins.

use forge_protocol::{PluginManifest, ProtocolError, PLATFORM_API_VERSION};
use semver::Version;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use thiserror::Error;
use walkdir::WalkDir;

#[derive(Debug, Error)]
pub enum CoreError {
    #[error(transparent)]
    Protocol(#[from] ProtocolError),
    #[error("plugin manifest scan failed: {0}")]
    Walk(#[from] walkdir::Error),
    #[error("duplicate plugin id {id}: {first} and {second}")]
    DuplicatePlugin {
        id: String,
        first: PathBuf,
        second: PathBuf,
    },
    #[error("plugin {plugin} requires missing capability {capability} {requirement}")]
    MissingCapability {
        plugin: String,
        capability: String,
        requirement: String,
    },
    #[error("plugin {plugin} requires {capability} {requirement}, but provider exposes {actual}")]
    IncompatibleCapability {
        plugin: String,
        capability: String,
        requirement: String,
        actual: String,
    },
    #[error("unsupported workspace schema version {0}")]
    UnsupportedWorkspaceVersion(u32),
    #[error("workspace I/O error: {0}")]
    Io(#[from] std::io::Error),
    #[error("workspace JSON error: {0}")]
    Json(#[from] serde_json::Error),
}

#[derive(Debug, Clone, Serialize)]
pub struct DiscoveredPlugin {
    pub root: PathBuf,
    pub manifest_path: PathBuf,
    pub manifest: PluginManifest,
    pub platform_compatible: bool,
}

#[derive(Debug, Default)]
pub struct PluginRegistry {
    plugins: BTreeMap<String, DiscoveredPlugin>,
}

impl PluginRegistry {
    pub fn discover(root: impl AsRef<Path>) -> Result<Self, CoreError> {
        let root = root.as_ref();
        let platform = Version::parse(PLATFORM_API_VERSION).expect("static platform version");
        let mut plugins = BTreeMap::new();

        if !root.exists() {
            return Ok(Self { plugins });
        }

        for entry in WalkDir::new(root).max_depth(3).follow_links(false) {
            let entry = entry?;
            if !entry.file_type().is_file() || entry.file_name() != "plugin.toml" {
                continue;
            }
            let manifest_path = entry.path().to_path_buf();
            let plugin_root = manifest_path
                .parent()
                .map(Path::to_path_buf)
                .unwrap_or_else(|| root.to_path_buf());
            let manifest = PluginManifest::from_path(&manifest_path)?;
            let platform_compatible = manifest.supports_platform(&platform)?;
            let id = manifest.id.clone();
            if let Some(existing) = plugins.get(&id) {
                return Err(CoreError::DuplicatePlugin {
                    id,
                    first: existing.manifest_path.clone(),
                    second: manifest_path,
                });
            }
            plugins.insert(
                id,
                DiscoveredPlugin {
                    root: plugin_root,
                    manifest_path,
                    manifest,
                    platform_compatible,
                },
            );
        }
        Ok(Self { plugins })
    }

    pub fn plugins(&self) -> impl Iterator<Item = &DiscoveredPlugin> {
        self.plugins.values()
    }

    pub fn get(&self, id: &str) -> Option<&DiscoveredPlugin> {
        self.plugins.get(id)
    }

    pub fn validate_dependencies(&self) -> Result<(), CoreError> {
        let mut capabilities = BTreeMap::<String, String>::new();
        for plugin in self.plugins.values() {
            for (name, version) in &plugin.manifest.provides {
                capabilities
                    .entry(name.clone())
                    .and_modify(|current| {
                        if Version::parse(version).ok() > Version::parse(current).ok() {
                            *current = version.clone();
                        }
                    })
                    .or_insert_with(|| version.clone());
            }
        }

        for plugin in self.plugins.values() {
            for (capability, requirement) in &plugin.manifest.requires {
                let Some(actual) = capabilities.get(capability) else {
                    return Err(CoreError::MissingCapability {
                        plugin: plugin.manifest.id.clone(),
                        capability: capability.clone(),
                        requirement: requirement.clone(),
                    });
                };
                let requirement_parsed = semver::VersionReq::parse(requirement)
                    .map_err(ProtocolError::from)?;
                let actual_parsed = Version::parse(actual).map_err(ProtocolError::from)?;
                if !requirement_parsed.matches(&actual_parsed) {
                    return Err(CoreError::IncompatibleCapability {
                        plugin: plugin.manifest.id.clone(),
                        capability: capability.clone(),
                        requirement: requirement.clone(),
                        actual: actual.clone(),
                    });
                }
            }
        }
        Ok(())
    }

    pub fn workbench_ids(&self) -> BTreeSet<String> {
        self.plugins
            .values()
            .flat_map(|p| p.manifest.contributes.workbenches.iter())
            .map(|w| w.id.clone())
            .collect()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceManifest {
    pub schema_version: u32,
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub enabled_plugins: Vec<String>,
    #[serde(default)]
    pub settings: serde_json::Value,
}

impl WorkspaceManifest {
    pub fn load(path: impl AsRef<Path>) -> Result<Self, CoreError> {
        let manifest: Self = serde_json::from_str(&std::fs::read_to_string(path)?)?;
        if manifest.schema_version != 1 {
            return Err(CoreError::UnsupportedWorkspaceVersion(manifest.schema_version));
        }
        Ok(manifest)
    }

    pub fn save(&self, path: impl AsRef<Path>) -> Result<(), CoreError> {
        let path = path.as_ref();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let temp = path.with_extension("tmp");
        std::fs::write(&temp, serde_json::to_vec_pretty(self)?)?;
        std::fs::rename(temp, path)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn workspace_round_trip() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time")
            .as_nanos();
        let path = std::env::temp_dir().join(format!("forge-workspace-{nonce}.json"));
        let workspace = WorkspaceManifest {
            schema_version: 1,
            id: "demo".into(),
            name: "Demo".into(),
            description: String::new(),
            enabled_plugins: vec!["hu.codelayer.pin-configurator".into()],
            settings: serde_json::json!({}),
        };
        workspace.save(&path).expect("save");
        let loaded = WorkspaceManifest::load(&path).expect("load");
        assert_eq!(loaded.name, "Demo");
        std::fs::remove_file(path).ok();
    }
}
