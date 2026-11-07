$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

foreach ($tool in @("uv", "python", "node", "npm")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Required tool '$tool' was not found. See README.md for prerequisites."
    }
}

$pythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$pythonVersion -lt [version]"3.12") { throw "Python 3.12+ is required." }
$nodeMajor = [int]((& node -p "process.versions.node.split('.')[0]").Trim())
if ($nodeMajor -lt 20) { throw "Node.js 20+ is required." }

& uv sync --directory (Join-Path $repoRoot "apps/api") --extra dev --locked
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& npm --prefix (Join-Path $repoRoot "apps/web") ci
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "NovelForge development dependencies are ready."
