param([Parameter(Mandatory=$true)][string]$OwnerPath)
$ErrorActionPreference='Stop'
if(-not (Test-Path -LiteralPath $OwnerPath)){exit 0}
$owner=Get-Content -LiteralPath $OwnerPath -Raw | ConvertFrom-Json
$live=Get-Process -Id ([int]$owner.pid) -ErrorAction SilentlyContinue
if(-not $live){exit 0}
if($live.StartTime.ToUniversalTime().Ticks.ToString() -ne [string]$owner.started -or
   $live.Path -ne [string]$owner.executable -or $live.ProcessName -ne 'EXCEL'){
 throw 'Excel ownership check failed; refusing to stop the process'
}
Stop-Process -Id $live.Id -Force -ErrorAction Stop
$live.WaitForExit(5000) | Out-Null
if(-not $live.HasExited){throw 'Owned Excel did not stop'}
