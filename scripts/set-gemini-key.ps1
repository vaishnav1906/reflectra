# Securely store a Gemini API key in backend/.env without echoing it.
# Usage: powershell -NoProfile -File scripts\set-gemini-key.ps1
$envFile = Join-Path $PSScriptRoot "..\backend\.env" | Resolve-Path

$secure = Read-Host "Paste your Gemini API key (input is hidden), then press Enter" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ([string]::IsNullOrWhiteSpace($key)) {
    Write-Host "No key entered; nothing changed." -ForegroundColor Yellow
    exit 1
}

$lines = [IO.File]::ReadAllLines($envFile)
$found = $false
$updated = foreach ($line in $lines) {
    if ($line -match '^GEMINI_API_KEY=') { $found = $true; "GEMINI_API_KEY=$key" } else { $line }
}
if (-not $found) { $updated = @($updated) + "GEMINI_API_KEY=$key" }

# UTF-8 without BOM, so python-dotenv reads it cleanly.
[IO.File]::WriteAllLines($envFile, [string[]]$updated, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ("Saved. Key length: {0} characters, starts with '{1}'." -f $key.Length, $key.Substring(0, [Math]::Min(3, $key.Length))) -ForegroundColor Green
