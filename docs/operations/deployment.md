# Enterprise Deployment

Recommended directories:

```text
installation/
  bin/
  resources/
  plugins/first-party/
organization-data/
  plugins/managed/
  policy.json
user-data/
  plugins/
  settings.json
  logs/
```

Scan plugin roots in trust order and never let a lower-trust plugin shadow an existing ID. Organization policy may disable user plugin roots, network access, USB/JTAG access and native runtimes. Store workspaces separately from executable plugins.
