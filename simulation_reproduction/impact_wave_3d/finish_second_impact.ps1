param(
    [Parameter(Mandatory=$true)][int]$SolverProcessId,
    [Parameter(Mandatory=$true)][string]$WorkDirectory,
    [Parameter(Mandatory=$true)][string]$PythonExecutable
)
$ErrorActionPreference = 'Stop'
$workPath = (Resolve-Path -LiteralPath $WorkDirectory).Path
$statePath = Join-Path $workPath 'finish_second_impact.status.json'
function Write-FinishState([string]$state, [string]$detail) {
    @{status=$state; detail=$detail; updated=(Get-Date -Format o); requested_hits=2} |
        ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8
}
try {
    Write-FinishState 'waiting_for_acc_n02' 'User requested finish second impact, push, then shut down. Third impact disabled by replacing the three-hit controller.'
    $solverProcess = Get-Process -Id $SolverProcessId -ErrorAction SilentlyContinue
    if ($solverProcess) { $solverProcess | Wait-Process }
    $lockPath = Join-Path $workPath 'acc_n02.lck'
    for ($attempt=0; $attempt -lt 60 -and (Test-Path -LiteralPath $lockPath); $attempt++) {
        Start-Sleep -Seconds 5
    }
    if (Test-Path -LiteralPath $lockPath) { throw 'Second impact lock remains after solver exit.' }
    $staPath = Join-Path $workPath 'acc_n02.sta'
    if (!(Test-Path -LiteralPath $staPath) -or
        !(Select-String -LiteralPath $staPath -SimpleMatch 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' -Quiet)) {
        throw 'Second impact did not finish successfully; preserve files and investigate.'
    }
    Write-FinishState 'reading_and_validating' 'Re-read completed chain with --hits 2; no third-hit submission.'
    & $PythonExecutable -u (Join-Path $PSScriptRoot 'run_repeat_impact.py') --production --hits 2 --work $workPath
    if ($LASTEXITCODE -ne 0) { throw "Two-hit result validation failed with exit code $LASTEXITCODE." }
    Write-FinishState 'ready_for_push' 'Two-hit metrics and handoff updated. Automation must verify push before shutdown.'
} catch {
    Write-FinishState 'failed' $_.Exception.Message
    throw
}
