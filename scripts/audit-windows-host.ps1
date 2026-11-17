# READ ONLY. Intended for a disposable Windows VM, not an installer.
# Avoids printing credentials or gateway key contents.
$ErrorActionPreference = 'Stop'
Write-Output '[JSC Commander] Read-only Windows host audit'
Write-Output ('Host: ' + [System.Environment]::MachineName)
Write-Output ('Identity: ' + [System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$principal = New-Object System.Security.Principal.WindowsPrincipal([System.Security.Principal.WindowsIdentity]::GetCurrent())
Write-Output ('AdministratorToken: ' + $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator))
$base = Join-Path $env:ProgramData 'JSCCommander'
foreach ($path in @($base, (Join-Path $base 'policy.json'), (Join-Path $base 'gateway.key'), (Join-Path $base 'State'))) {
  Write-Output ('\nPath: ' + $path)
  if (Test-Path -LiteralPath $path) {
    Get-Acl -LiteralPath $path | Select-Object Owner, AreAccessRulesProtected | Format-List | Out-String | Write-Output
    # ACE entries can still expose account names: output only to a local protected log.
    Write-Output ('ACL entries: ' + (Get-Acl -LiteralPath $path).Access.Count)
  } else {
    Write-Output 'NOT FOUND'
  }
}
Write-Output 'NOTE: This script does not verify effective rights or security isolation; external ACL audit required.'
