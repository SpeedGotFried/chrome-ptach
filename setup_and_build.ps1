# Setup and Build Custom Chromium Script
# Run this script in PowerShell as Administrator on Windows.

$BuildDir = "C:\chromium"
$DepotToolsDir = "C:\src\depot_tools"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "   Custom Chromium Build Automation Script     " -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1. Check/Install depot_tools
if (-not (Test-Path $DepotToolsDir)) {
    Write-Host "[+] Creating Depot Tools directory..." -ForegroundColor Green
    New-Item -ItemType Directory -Path (Split-Path $DepotToolsDir -Parent) -Force | Out-Null
    
    Write-Host "[+] Downloading depot_tools.zip..." -ForegroundColor Green
    $ZipPath = Join-Path (Split-Path $DepotToolsDir -Parent) "depot_tools.zip"
    Invoke-WebRequest -Uri "https://storage.googleapis.com/chrome-infra/depot_tools.zip" -OutFile $ZipPath
    
    Write-Host "[+] Unzipping depot_tools..." -ForegroundColor Green
    Expand-Archive -Path $ZipPath -DestinationPath $DepotToolsDir -Force
    Remove-Item $ZipPath
} else {
    Write-Host "[*] Depot Tools already installed at $DepotToolsDir" -ForegroundColor Yellow
}

# 2. Add Depot Tools to PATH
$CurrentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($CurrentPath -notlike "*depot_tools*") {
    Write-Host "[+] Adding Depot Tools to User PATH environment variable..." -ForegroundColor Green
    $NewPath = "$DepotToolsDir;" + $CurrentPath
    [Environment]::SetEnvironmentVariable("PATH", $NewPath, "User")
    $env:PATH = "$DepotToolsDir;" + $env:PATH
}

# 3. Configure local build toolchain variables
Write-Host "[+] Setting up environment variables..." -ForegroundColor Green
[Environment]::SetEnvironmentVariable("DEPOT_TOOLS_WIN_TOOLCHAIN", "0", "User")
$env:DEPOT_TOOLS_WIN_TOOLCHAIN = "0"

# 4. Fetch Chromium source code
if (-not (Test-Path $BuildDir)) {
    Write-Host "[+] Creating Chromium build directory: $BuildDir" -ForegroundColor Green
    New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
}

Set-Location $BuildDir
if (-not (Test-Path "src")) {
    Write-Host "[+] Fetching Chromium source code (this will take a while, ~15-30GB download)..." -ForegroundColor Green
    # Force execution in standard Cmd to leverage gclient/fetch wrappers
    cmd.exe /c "fetch --no-history chromium"
} else {
    Write-Host "[*] Chromium source code already present." -ForegroundColor Yellow
}

# 5. Apply the Bypass Patch
Set-Location "$BuildDir\src"
$PatchFilePath = Join-Path $PSScriptRoot "chromium_focus_bypass.patch"
if (Test-Path $PatchFilePath) {
    Write-Host "[+] Applying focus/visibility bypass patch..." -ForegroundColor Green
    # Check if patch is already applied
    $PatchCheck = git apply --check $PatchFilePath 2>&1
    if ($null -eq $PatchCheck -or $PatchCheck -notlike "*error*") {
        git apply $PatchFilePath
        Write-Host "[+] Patch applied successfully!" -ForegroundColor Green
    } else {
        Write-Host "[*] Patch check failed. It might already be applied or conflicts exist." -ForegroundColor Yellow
    }
} else {
    Write-Warning "[-] Patch file 'chromium_focus_bypass.patch' not found in script directory. Please place it next to this script."
}

# 6. Generate optimized release args and configuration
Write-Host "[+] Generating GN build files..." -ForegroundColor Green
cmd.exe /c "gn gen out\Default"

$ArgsFile = "out\Default\args.gn"
$ArgsContent = @"
is_debug = false
is_component_build = false
symbol_level = 0
blink_symbol_level = 0
"@

if (Test-Path $ArgsFile) {
    Write-Host "[+] Configuring GN build arguments..." -ForegroundColor Green
    Set-Content -Path $ArgsFile -Value $ArgsContent
}

# 7. Compile Chrome
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Preparation complete. Compiling Chromium..." -ForegroundColor Cyan
Write-Host "This process is heavy and will take several hours." -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
cmd.exe /c "autoninja -C out\Default mini_installer"

Write-Host "[+] Compilation finished! The installer is located under out\Default\mini_installer.exe" -ForegroundColor Green
