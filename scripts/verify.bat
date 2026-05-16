@echo off
REM SYLION v6.2.0 verify (Windows CMD)
setlocal
set "BASE=http://127.0.0.1:8422"
if not "%SYLION_BASE%"=="" set "BASE=%SYLION_BASE%"

echo ==^> SYLION v6.2.0 verify @ %BASE%
echo.

where curl >nul 2>&1
if errorlevel 1 (
  echo [ERROR] curl nie znaleziony. Zainstaluj curl lub uzyj verify.ps1
  exit /b 1
)

set /a pass=0
set /a fail=0

REM Test 1: /api/health
curl -sf "%BASE%/api/health" 2>nul | findstr "6.2.0" >nul
if errorlevel 1 (
  echo     [FAIL] /api/health
  set /a fail+=1
) else (
  echo     [PASS] /api/health 200 + version=6.2.0
  set /a pass+=1
)

REM Test 2: /api/version
curl -sf "%BASE%/api/version" 2>nul | findstr "\"version\":\"6.2.0\"" >nul
if errorlevel 1 (
  echo     [FAIL] /api/version
  set /a fail+=1
) else (
  echo     [PASS] /api/version == 6.2.0
  set /a pass+=1
)

REM Test 3: /api/auth/setup-status (B-003)
curl -sf "%BASE%/api/auth/setup-status" >nul 2>&1
if errorlevel 1 (
  echo     [FAIL] /api/auth/setup-status
  set /a fail+=1
) else (
  echo     [PASS] /api/auth/setup-status (B-003 alias)
  set /a pass+=1
)

REM Test 4: dash canonical
curl -s -o nul -w "%%{http_code}" "%BASE%/api/human-gate/queue" 2>nul > "%TEMP%\sylion_code.txt"
set /p CODE=<"%TEMP%\sylion_code.txt"
del "%TEMP%\sylion_code.txt" 2>nul
if "%CODE%"=="401" (
  echo     [PASS] /api/human-gate/queue canonical
  set /a pass+=1
) else if "%CODE%"=="200" (
  echo     [PASS] /api/human-gate/queue canonical
  set /a pass+=1
) else (
  echo     [FAIL] /api/human-gate/queue HTTP=%CODE%
  set /a fail+=1
)

REM Test 5: deprecated underscore
curl -s -D - "%BASE%/api/human_gate/queue" 2>nul | findstr /i "^deprecation" >nul
if errorlevel 1 (
  echo     [FAIL] /api/human_gate/queue brak deprecation header
  set /a fail+=1
) else (
  echo     [PASS] /api/human_gate/queue ma deprecation header
  set /a pass+=1
)

echo.
echo Result: %pass% PASS, %fail% FAIL
(endlocal & exit /b %fail%)
