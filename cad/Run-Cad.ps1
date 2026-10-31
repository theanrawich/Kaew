param(
    [ValidateSet('BuildSpout','VerifySpout','BuildAssembly','CheckAssembly')]
    [string]$Task = 'BuildAssembly',
    [string]$FreeCADCmd
)
$ErrorActionPreference = 'Stop'
if (-not $FreeCADCmd) {
    $kaewCadCommand = Get-Command FreeCADCmd,freecadcmd.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($kaewCadCommand) { $FreeCADCmd = $kaewCadCommand.Source }
}
if (-not $FreeCADCmd) {
    $kaewInstallRoots = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\FreeCAD 1.1\bin\freecadcmd.exe'),
        (Join-Path $env:ProgramFiles 'FreeCAD 1.1\bin\freecadcmd.exe')
    )
    $FreeCADCmd = $kaewInstallRoots | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $FreeCADCmd -or -not (Test-Path -LiteralPath $FreeCADCmd)) {
    throw 'Install FreeCAD 1.1.4 or pass -FreeCADCmd with its executable path.'
}
$kaewTaskFiles = @{
    BuildSpout = 'spout-v1\build_spout.py'
    VerifySpout = 'spout-v1\verify_exports.py'
    BuildAssembly = 'full-assembly-v1\build_assembly.py'
    CheckAssembly = 'full-assembly-v1\check_fit.py'
}
$kaewTaskScript = Join-Path $PSScriptRoot $kaewTaskFiles[$Task]
$kaewTaskLog = Join-Path (Split-Path -Parent $kaewTaskScript) ($Task + '.log')
& $FreeCADCmd $kaewTaskScript *> $kaewTaskLog
$kaewResult = $LASTEXITCODE
Get-Content -LiteralPath $kaewTaskLog -Tail 40
if ($kaewResult -ne 0 -or (Select-String -LiteralPath $kaewTaskLog -Pattern 'Exception while processing file:|Traceback \(most recent call last\)|Invalid BRep:|RuntimeError:' -Quiet)) {
    throw ('FreeCAD task failed. Read ' + $kaewTaskLog)
}
Write-Output ('Completed ' + $Task + '. Inspect generated reports before claiming the design fits.')
