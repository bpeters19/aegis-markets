# Loads the 64-bit MSVC toolchain (cl, cmake, ninja) into the current PowerShell session.
# Usage, from the repo root:  .\scripts\cpp-env.ps1
$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
$vs = & $vswhere -latest -products * -property installationPath
if (-not $vs) { throw "Visual Studio Build Tools not found." }
Import-Module (Join-Path $vs "Common7\Tools\Microsoft.VisualStudio.DevShell.dll")
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments "-arch=x64 -host_arch=x64" | Out-Null
Write-Host "64-bit MSVC toolchain ready: $((Get-Command cl).Source)"
