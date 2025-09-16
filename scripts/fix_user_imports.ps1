param(
  [switch]$Apply  # use -Apply to write changes; default = dry-run
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Write-Host "Project root: $Root"
$pyFiles = Get-ChildItem -Path $Root -Recurse -Include *.py -File

$changedFiles = @()

foreach ($f in $pyFiles) {
  $raw = Get-Content -Raw -Encoding UTF8 -Path $f.FullName
  $orig = $raw
  # Normalize to `n for processing
  $lines = $raw -replace "`r`n","`n" -split "`n"

  $out = New-Object System.Collections.Generic.List[string]

  foreach ($line in $lines) {
    $trim = $line.Trim()
    # 1) Handle "from users.models import ..." lines
    if ($trim -match '^\s*from\s+users\.models\s+import\s+(.+)$') {
      $imports = $matches[1] -split ',' | ForEach-Object { $_.Trim() }
      if ($imports -contains 'Notification') {
        $out.Add('from users.models import Notification')
      } else {
        # drop the import that imports User (no replacement)
      }
      continue
    }

    # 2) Remove assignments that set User to AUTH_USER_MODEL string or literal
    if ($trim -match '^\s*User\s*=\s*(settings\.AUTH_USER_MODEL|["''].*?["''])\s*$') {
      # drop this line
      continue
    }

    $out.Add($line)
  }

  $modified = ($out -join "`n")

  # 3) Insert get_user_model() if file references User.* and doesn't already have get_user_model or define User class
  $refsUser = ($modified -match '\bUser\.(objects\b|objects\s*\(|\bobjects\b|\bUser\b)') # rough check for usage
  $hasGetUser = ($modified -match 'get_user_model\s*\(')
  $definesUserClass = ($modified -match 'class\s+User\b')
  if ($refsUser -and -not $hasGetUser -and -not $definesUserClass) {
    # avoid modifying the users/models.py file itself
    if ($f.FullName -notmatch "\\users\\models\.py$") {
      # choose injection point: after initial block of imports
      $lines2 = $modified -split "`n"
      $insertAt = 0
      for ($i=0; $i -lt $lines2.Length; $i++) {
        if ($lines2[$i] -match '^\s*(from\s+\w+|import\s+\w+)') {
          $insertAt = $i + 1
        } else {
          # stop scanning after first non-imports after a few lines
          if ($i -gt 50) { break }
        }
      }
      $inject = "from django.contrib.auth import get_user_model`nUser = get_user_model()`n"
      # only inject if not already present
      if ($modified -notmatch [regex]::Escape("User = get_user_model()")) {
        $before = $lines2[0..($insertAt-1)]
        $after = @()
        if ($insertAt -le $lines2.Length - 1) {
          $after = $lines2[$insertAt..($lines2.Length-1)]
        }
        $newLines = @()
        $newLines += $before
        $newLines += $inject
        $newLines += $after
        $modified = ($newLines -join "`n")
      }
    }
  }

  if ($modified -ne $orig) {
    $changedFiles += $f.FullName
    if ($Apply) {
      Copy-Item -Path $f.FullName -Destination ($f.FullName + ".bak") -Force
      Set-Content -Path $f.FullName -Value ($modified -replace "`n", [Environment]::NewLine) -Encoding UTF8
      Write-Host "Updated: $($f.FullName)" -ForegroundColor Green
    } else {
      Write-Host "Would modify: $($f.FullName)" -ForegroundColor Yellow
    }
  }
}

if ($changedFiles.Count -eq 0) {
  Write-Host "No issues found."
} else {
  Write-Host ""
  Write-Host "Files detected for change:" -ForegroundColor Cyan
  $changedFiles | ForEach-Object { Write-Host " - $_" }
  if (-not $Apply) {
    Write-Host ""
    Write-Host "Dry-run complete. To apply changes run this script with the -Apply switch:" -ForegroundColor Cyan
    Write-Host "powershell -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Definition)`" -Apply"
  } else {
    Write-Host ""
    Write-Host "Applied changes. Backups saved with .bak extension." -ForegroundColor Green
  }
}