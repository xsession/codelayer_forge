$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 (Join-Path $ScriptDir "bootstrap.py") @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python (Join-Path $ScriptDir "bootstrap.py") @args
} else {
    throw "Python 3.9+ was not found. Install Python and retry."
}
exit $LASTEXITCODE
