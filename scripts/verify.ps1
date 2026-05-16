# SYLION v6.2.0 verify (PowerShell)
$Base = if ($env:SYLION_BASE) { $env:SYLION_BASE } else { "http://127.0.0.1:8422" }

Write-Host "==> SYLION v6.2.0 verify @ $Base" -ForegroundColor Cyan
Write-Host ""

$pass = 0; $fail = 0

function Invoke-Safe {
    param([string]$Url)
    try {
        return Invoke-WebRequest -Uri $Url -TimeoutSec 10 -ErrorAction Stop
    } catch {
        $ex = $_.Exception
        if ($ex.Response) { return $ex.Response }
        return $null
    }
}

function Get-HeaderValue {
    param($Response, [string]$Name)
    if ($null -eq $Response) { return $null }
    $target = $Name.ToLower()
    try {
        $h = $Response.Headers
        if ($null -ne $h) {
            # pwsh 7: HttpResponseHeaders - iteracja przez GetEnumerator()
            if ($h -is [System.Net.Http.Headers.HttpHeaders]) {
                # TryGetValues - najpewniejsza sciezka
                $values = $null
                $null = $h.TryGetValues($Name, [ref]$values)
                if ($null -ne $values) {
                    $arr = @($values)
                    if ($arr.Count -gt 0) { return "$($arr[0])" }
                }
                # Fallback: iteracja KeyValuePair
                foreach ($kvp in $h) {
                    if ("$($kvp.Key)".ToLower() -eq $target) {
                        $arr = @($kvp.Value)
                        if ($arr.Count -gt 0) { return "$($arr[0])" }
                    }
                }
            }
            # Windows PowerShell 5.1: IDictionary[string, string[]]
            elseif ($h -is [System.Collections.IDictionary]) {
                foreach ($k in @($h.Keys)) {
                    if ("$k".ToLower() -eq $target) {
                        $v = $h[$k]
                        if ($v -is [array]) { return "$($v[0])" }
                        return "$v"
                    }
                }
            }
        }
        # Ostatecznie: BaseResponse (WebResponse legacy)
        if ($Response.PSObject.Properties['BaseResponse']) {
            $br = $Response.BaseResponse
            if ($null -ne $br -and $null -ne $br.Headers) {
                foreach ($k in @($br.Headers.AllKeys)) {
                    if ("$k".ToLower() -eq $target) { return "$($br.Headers[$k])" }
                }
            }
        }
    } catch { }
    return $null
}

function Test-Check {
    param([string]$Name, [scriptblock]$Block)
    try {
        if (& $Block) {
            Write-Host "    [PASS] $Name" -ForegroundColor Green
            $script:pass++
        } else {
            Write-Host "    [FAIL] $Name" -ForegroundColor Red
            $script:fail++
        }
    } catch {
        Write-Host "    [FAIL] $Name ($_)" -ForegroundColor Red
        $script:fail++
    }
}

Test-Check "/api/health 200 + version=6.2.0" {
    $r = Invoke-Safe "$Base/api/health"
    $null -ne $r -and "$($r.Content)" -match "6\.2\.0"
}

Test-Check "/api/version == 6.2.0" {
    $r = Invoke-Safe "$Base/api/version"
    $null -ne $r -and "$($r.Content)" -match '"version":"6\.2\.0"'
}

Test-Check "/api/auth/setup-status (B-003 alias)" {
    $r = Invoke-Safe "$Base/api/auth/setup-status"
    $null -ne $r -and [int]$r.StatusCode -eq 200
}

Test-Check "/api/human-gate/queue canonical" {
    $r = Invoke-Safe "$Base/api/human-gate/queue"
    if ($null -eq $r) { return $false }
    $code = [int]$r.StatusCode
    $code -eq 200 -or $code -eq 401 -or $code -eq 403
}

Test-Check "/api/human_gate/queue ma deprecation header" {
    $r = Invoke-Safe "$Base/api/human_gate/queue"
    if ($null -eq $r) { return $false }
    $dep = Get-HeaderValue $r "Deprecation"
    if ($null -eq $dep -or "$dep".Length -eq 0) {
        # Diagnostyka: wypisz wszystkie naglowki zeby widziec format
        Write-Host "    [DIAG] Headers dump (type=$($r.Headers.GetType().FullName)):" -ForegroundColor Yellow
        try {
            foreach ($kvp in $r.Headers) {
                Write-Host "      $($kvp.Key) = $($kvp.Value -join ',')" -ForegroundColor Yellow
            }
        } catch { Write-Host "      (iteracja zawiodla: $_)" -ForegroundColor Yellow }
        return $false
    }
    $true
}

Write-Host ""
$color = if ($fail -eq 0) { "Green" } else { "Red" }
Write-Host "Result: $pass PASS, $fail FAIL" -ForegroundColor $color
exit $fail
