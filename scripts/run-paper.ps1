# Runs the daily paper-trading runner and appends its output to logs/paper-run.log.
# Used by the "Aegis Paper Run" scheduled task; safe to run by hand too.
$root = Split-Path -Parent $PSScriptRoot
$log = Join-Path $root "logs\paper-run.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

Set-Location (Join-Path $root "backend")
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Add-Content $log
& .\.venv\Scripts\python.exe -m app.paper.run *>> $log
$code = $LASTEXITCODE
"exit code $code" | Add-Content $log
exit $code
