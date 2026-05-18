param(
    [string]$Container,
    [string]$CustomTag,
    [string]$TagSuffix,
    [string]$RegistryHost,
    [string]$ImageOwner,
    [string]$StackEnvPath = "../stack/.env",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

function Read-DotEnv {
    param([string]$Path)
    $vars = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $vars
    }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $key, $value = $line -split "=", 2
        $vars[$key.Trim()] = $value.Trim()
    }
    return $vars
}

function Normalize-RegistryHost {
    param([string]$HostValue)
    $hostOnly = $HostValue -replace "^https?://", ""
    $hostOnly = ($hostOnly -split "/", 2)[0]
    if ($hostOnly -and -not $hostOnly.Contains(":")) {
        $hostOnly = "${hostOnly}:5000"
    }
    return $hostOnly
}

function Get-VersionTag {
    param([string]$Override)
    if ($Override) {
        $clean = $Override -replace "[^A-Za-z0-9_.-]", "-"
        if ($clean -notmatch "^[A-Za-z0-9]") {
            $clean = "v$clean"
        }
        return $clean
    }

    $message = (git log -1 --pretty=%s 2>$null)
    Write-Host "Commit message: $message"
    $match = [regex]::Matches($message, "v[0-9]+(\.[0-9]+)*\.[Rr][Cc][0-9]+") | Select-Object -Last 1
    if ($match) {
        $version = $match.Value.ToLowerInvariant()
    }
    else {
        $sha = (git rev-parse --short HEAD).Trim()
        $version = "dev-$sha"
    }

    $clean = $version -replace "[^a-z0-9_.-]", "-"
    if ($clean -notmatch "^[a-z0-9]") {
        $clean = "v$clean"
    }
    return $clean
}

function Normalize-TagPart {
    param(
        [string]$Value,
        [bool]$Lowercase = $true
    )
    $clean = $Value -replace "[^A-Za-z0-9_.-]", "-"
    if ($Lowercase) {
        $clean = $clean.ToLowerInvariant()
    }
    $clean = $clean.Trim("-")
    return $clean
}

function Get-EnvKeyForBase {
    param([string]$Base)
    $map = @{
        "ai_kit"          = "AI_KIT_TAG"
        "bag_recorder"    = "BAG_RECORDER_TAG"
        "bridge"          = "BRIDGE_TAG"
        "camera"          = "CAMERA_TAG"
        "db"              = "DB_TAG"
        "foxglove_bridge" = "FOXGLOVE_BRIDGE_TAG"
        "healthcheck"     = "HEALTHCHECK_TAG"
        "laser_driver"    = "DRIVER_TAG"
        "nav"             = "NAV_TAG"
        "realsense"       = "REALSENSE_TAG"
        "rosbridge"       = "ROSBRIDGE_TAG"
        "sensor_fusion"   = "SENSOR_FUSION_TAG"
        "slam"            = "SLAM_TAG"
    }
    return $map[$Base]
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$envPath = $StackEnvPath
if (-not [System.IO.Path]::IsPathRooted($envPath)) {
    $envPath = Join-Path $repoRoot $envPath
}
$dotenv = Read-DotEnv -Path $envPath

if (-not $RegistryHost) {
    $RegistryHost = $env:REGISTRY_HOST
}
if (-not $RegistryHost -and $dotenv.ContainsKey("REGISTRY_HOST")) {
    $RegistryHost = $dotenv["REGISTRY_HOST"]
}
if (-not $ImageOwner) {
    $ImageOwner = $env:IMAGE_OWNER
}
if (-not $ImageOwner -and $dotenv.ContainsKey("IMAGE_OWNER")) {
    $ImageOwner = $dotenv["IMAGE_OWNER"]
}

$RegistryHost = Normalize-RegistryHost $RegistryHost
if (-not $RegistryHost) {
    throw "Registry host missing. Set REGISTRY_HOST or pass -RegistryHost."
}
if (-not $ImageOwner) {
    throw "Image owner missing. Set IMAGE_OWNER or pass -ImageOwner."
}
$ImageOwner = $ImageOwner.ToLowerInvariant()

$containers = Get-ChildItem -Directory |
Where-Object { Test-Path (Join-Path $_.FullName "Dockerfile") } |
Select-Object -ExpandProperty Name |
Sort-Object

if (-not $Container) {
    Write-Host "Available containers:"
    for ($i = 0; $i -lt $containers.Count; $i++) {
        Write-Host ("  {0,2}. {1}" -f ($i + 1), $containers[$i])
    }
    $choice = Read-Host "Which container do you want to build? Enter number or name"
    if ($choice -match "^\d+$") {
        $index = [int]$choice - 1
        if ($index -lt 0 -or $index -ge $containers.Count) {
            throw "Invalid container number: $choice"
        }
        $Container = $containers[$index]
    }
    else {
        $Container = $choice.Trim()
    }
}

if ($containers -notcontains $Container) {
    throw "Unknown container '$Container' or missing Dockerfile."
}

$base = if ($Container.EndsWith("_cont")) { $Container.Substring(0, $Container.Length - 5) } else { $Container }
$versionTag = Get-VersionTag -Override $CustomTag
if (-not $TagSuffix) {
    $TagSuffix = Read-Host "Optional tag suffix to avoid overwriting an existing tag (blank = none)"
}
if ($TagSuffix) {
    $suffix = Normalize-TagPart -Value $TagSuffix
    if ($suffix) {
        $versionTag = "$versionTag-$suffix"
    }
}
$tag = "${base}-${versionTag}"
$image = "${RegistryHost}/${ImageOwner}/${base}:${tag}"
$envKey = Get-EnvKeyForBase -Base $base

Write-Host ""
Write-Host "Build context : $Container"
Write-Host "Dockerfile    : $Container/Dockerfile"
Write-Host "Platform      : linux/arm64"
Write-Host "Image         : $image"
if ($envKey) {
    Write-Host "Stack .env    : $envKey=$tag"
}
Write-Host ""

$confirm = Read-Host "Build and $(if ($NoPush) { 'load locally' } else { 'push' }) this image? [y/N]"
if ($confirm -notmatch "^(y|yes)$") {
    Write-Host "Cancelled."
    exit 0
}

$args = @(
    "buildx", "build",
    "--platform", "linux/arm64",
    "--file", "$Container/Dockerfile",
    "--tag", $image
)
if ($NoPush) {
    $args += "--load"
}
else {
    $args += "--push"
}
$args += $Container

docker @args

Write-Host ""
Write-Host "Done: $image"
if ($envKey) {
    Write-Host "Set this in stack/.env:"
    Write-Host "$envKey=$tag"
}
