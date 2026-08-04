# Plugin Capability Broker

The broker discovers first-party plugins, validates capability providers and command ownership, starts plugin hosts lazily and keeps them alive across requests. It exposes `forge/executeCommand` and `forge/callCapability` over newline-delimited JSON-RPC 2.0.

```bash
python3 hosts/plugin-broker/forge_broker.py \
  --plugins-root plugins \
  --workspace examples/demo-workspace
```

The broker is the platform integration boundary: callers select a capability, not a provider implementation.
