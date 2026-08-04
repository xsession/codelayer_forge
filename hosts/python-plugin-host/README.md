# Python Plugin Host

This process loads one Python plugin and communicates over newline-delimited JSON-RPC 2.0 on standard input/output. Logs are sent to standard error. A host process is intentionally dedicated to one plugin so dependency conflicts or crashes remain isolated.
