# Plugin Lifecycle

1. **Discovery**: the registry scans bounded plugin roots for `plugin.toml`.
2. **Validation**: identity, semantic versions, platform API range and capability requirements are checked.
3. **Activation**: a host process imports the declared entrypoint and calls `activate(context)`.
4. **Registration**: the plugin registers command handlers and versioned services.
5. **Invocation**: the desktop or CLI dispatches JSON-RPC calls to the host.
6. **Deactivation**: the host calls `deactivate()` and terminates the dedicated process.
7. **Recovery**: a failed process can be restarted without losing the desktop shell.

Activation events are declarative metadata in this release. Lazy activation policy is the next host responsibility; first-party plugins currently start only when explicitly invoked.
