# Plugin Development

Create a directory under a configured plugin root:

```text
my-plugin/
├── plugin.toml
├── README.md
└── src/my_plugin/
    ├── __init__.py
    └── plugin.py
```

A minimal plugin:

```python
class ExamplePlugin:
    def activate(self, context):
        context.commands.register("example.hello", lambda args: {"message": "hello"})

    def deactivate(self):
        pass


def create_plugin():
    return ExamplePlugin()
```

Declare `entrypoint = "my_plugin.plugin:create_plugin"` and run:

```bash
python3 hosts/python-plugin-host/forge_plugin_host.py --plugin-dir path/to/my-plugin
```

Send newline-delimited JSON-RPC messages on stdin. Never print to stdout from plugin code; use `context.logger`.
