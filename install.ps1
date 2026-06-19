$ErrorActionPreference = "Stop"

$Repo       = "paulushcgcj/sqlfy"
$Binary     = "sqlfy"
$InstallDir = "$env:LOCALAPPDATA\Programs\$Binary"

$release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
$version = $release.tag_name
$url     = "https://github.com/$Repo/releases/download/$version/$Binary-windows-x86_64.exe"

Write-Host "-> Installing $Binary $version"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Invoke-WebRequest -Uri $url -OutFile "$InstallDir\$Binary.exe"

$current = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($current -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$current;$InstallDir", "User")
    Write-Host "Added $InstallDir to PATH (restart your terminal)"
}

Write-Host "Done. Run: $Binary --help"
