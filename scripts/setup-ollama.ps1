param([string]$Model = 'qwen3-vl:8b-instruct')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if ($Model -match '^qwen3-vl:' -and $Model -notmatch 'instruct') {
    throw 'Use qwen3-vl:8b-instruct for this project. The default Qwen3-VL tag is a thinking model.'
}
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw 'Install Ollama from https://ollama.com/download first.'
}
& ollama pull $Model
if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Run again to resume.' }
$details = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/show' -Method Post -ContentType 'application/json' -Body (@{model=$Model} | ConvertTo-Json)
if ($details.capabilities -notcontains 'vision') { throw 'A vision-capable model is required.' }
$values = [ordered]@{
    QC_PROVIDER='ollama'
    QC_OLLAMA_BASE='http://127.0.0.1:11434'
    QC_MODEL=$Model
    QC_ENHANCED_MODEL=''
    QC_ENABLE_LIVE='1'
    QC_TIMEOUT_SEC='300'
    QC_OLLAMA_NUM_CTX='16384'
}
$configPath = Join-Path $projectRoot '.env'
$lines = @()
if (Test-Path -LiteralPath $configPath) {
    $lines = @([IO.File]::ReadAllLines($configPath) | Where-Object {
        $key = ($_ -split '=', 2)[0].Trim()
        -not $values.Contains($key)
    })
}
foreach ($key in $values.Keys) { $lines += "$key=$($values[$key])" }
[IO.File]::WriteAllLines($configPath, $lines, [Text.UTF8Encoding]::new($false))
Write-Host "Configured local Ollama model: $Model"
Write-Host 'Restart FrameProof, then open http://127.0.0.1:8765'
Write-Host 'Real inference check: .venv\Scripts\python scripts\ollama_smoke.py'
