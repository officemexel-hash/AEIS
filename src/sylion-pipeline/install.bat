@echo off
:: =============================================================================
:: SYLION v5.9.2 — Windows Installer (cmd.exe)
:: Audit: 2026-07-11 | R3.13: unified runtime entrypoint
::
:: USAGE:
::   install_v592.bat                              normal install
::   install_v592.bat --dry-run                    simulate, no changes
::   install_v592.bat --reinstall                  wipe venv+DB and reinstall
::   set PYTHON_BIN=python3.12 && install_v592.bat override interpreter
::   set SYLION_PORT=8422      && install_v592.bat override port
::
:: IDEMPOTENT: Safe to re-run multiple times.
:: ROLLBACK:   On failure, partially created venv is cleaned up.
:: Run as Administrator for system-wide installation.
:: =============================================================================
setlocal enabledelayedexpansion

:: ---------------------------------------------------------------------------
:: Configuration (override via SET before running)
:: ---------------------------------------------------------------------------
if not defined PYTHON_BIN    set "PYTHON_BIN=python"
if not defined VENV_DIR      set "VENV_DIR=.venv"
if not defined REQ_FILE      set "REQ_FILE=requirements-lock.txt"
if not defined AGENTS_YAML   set "AGENTS_YAML=agents.yaml"
if not defined SYLION_PORT   set "SYLION_PORT=8421"
if not defined SYLION_LOG    set "SYLION_LOG=%USERPROFILE%\sylion\install.log"

set "SCRIPT_VERSION=5.9.2"
set "HEALTH_URL=http://127.0.0.1:!SYLION_PORT!/health"
set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=!VENV_DIR!\Scripts\python.exe"
set "VENV_PIP=!VENV_DIR!\Scripts\pip.exe"
set "SETUP_TOKEN_FILE=SETUP_TOKEN.txt"

set "MIN_MAJOR=3"
set "MIN_MINOR=11"
set "MIN_DISK_MB=500"

:: Runtime flags
set "DRY_RUN=0"
set "REINSTALL=0"
set "INSTALL_FAILED=0"
set "VENV_CREATED=0"

:: ---------------------------------------------------------------------------
:: Parse CLI arguments
:: ---------------------------------------------------------------------------
:parse_loop
if "%~1"=="" goto :parse_done
if /i "%~1"=="--dry-run"   set "DRY_RUN=1"   && shift && goto :parse_loop
if /i "%~1"=="--reinstall" set "REINSTALL=1"  && shift && goto :parse_loop
if /i "%~1"=="--help"      goto :show_help
if /i "%~1"=="-h"          goto :show_help
call :log_error "Unknown argument: %~1 (use --help)"
goto :fail
:parse_done

goto :main

:show_help
echo.
echo USAGE: install_v592.bat [--dry-run] [--reinstall] [--help]
echo.
echo   --dry-run      Simulate all steps; no filesystem changes.
echo   --reinstall    Wipe venv + backup DB, then reinstall fresh.
echo.
endlocal
exit /b 0

:: ---------------------------------------------------------------------------
:: MAIN
:: ---------------------------------------------------------------------------
:main
cd /d "!SCRIPT_DIR!"

:: Setup log directory and file
if !DRY_RUN! equ 0 (
    for %%D in ("!SYLION_LOG!") do (
        if not exist "%%~dpD" mkdir "%%~dpD" 2>nul
    )
)

call :log_banner

:: Preflight
call :preflight_python  || goto :fail
call :preflight_pip     || goto :fail
call :preflight_disk    || goto :fail

:: Reinstall prep
if !REINSTALL! equ 1 call :handle_reinstall

:: Install steps
call :create_venv       || goto :fail
call :install_deps      || goto :fail
call :init_database     || goto :fail
call :generate_token    || goto :fail
call :seed_agents
call :healthcheck

call :print_next_steps
goto :done

:: ---------------------------------------------------------------------------
:log_banner
echo.
echo ============================================================
echo   SYLION v!SCRIPT_VERSION! -- Installer (Windows)
if !DRY_RUN! equ 1   echo   MODE: DRY-RUN (no changes will be made)
if !REINSTALL! equ 1 echo   MODE: REINSTALL (wipe + fresh install)
echo   Log: !SYLION_LOG!
echo ============================================================
echo.
goto :eof

:: ---------------------------------------------------------------------------
:: Preflight: Python version
:: ---------------------------------------------------------------------------
:preflight_python
call :log_info "Preflight: checking Python interpreter..."

where !PYTHON_BIN! >nul 2>&1
if !errorlevel! neq 0 (
    call :log_error "Python not found: !PYTHON_BIN!"
    call :log_error "Install Python 3.11+ from https://python.org and add to PATH."
    exit /b 1
)

for /f "tokens=*" %%V in ('!PYTHON_BIN! -c "import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")" 2^>nul') do (
    set "PY_VER=%%V"
)

if not defined PY_VER (
    call :log_error "Could not determine Python version."
    exit /b 1
)

for /f "tokens=1,2 delims=." %%A in ("!PY_VER!") do (
    set "PY_MAJOR=%%A"
    set "PY_MINOR=%%B"
)

if !PY_MAJOR! LSS !MIN_MAJOR! (
    call :log_error "Python !PY_VER! is too old. Minimum required: !MIN_MAJOR!.!MIN_MINOR!"
    exit /b 1
)
if !PY_MAJOR! EQU !MIN_MAJOR! if !PY_MINOR! LSS !MIN_MINOR! (
    call :log_error "Python !PY_VER! is too old. Minimum required: !MIN_MAJOR!.!MIN_MINOR!"
    exit /b 1
)

call :log_ok "Python !PY_VER! found."
goto :eof

:: ---------------------------------------------------------------------------
:: Preflight: pip availability
:: ---------------------------------------------------------------------------
:preflight_pip
call :log_info "Preflight: checking pip availability..."
!PYTHON_BIN! -m pip --version >nul 2>&1
if !errorlevel! neq 0 (
    call :log_error "pip not available. Run: !PYTHON_BIN! -m ensurepip"
    exit /b 1
)
call :log_ok "pip is available."
goto :eof

:: ---------------------------------------------------------------------------
:: Preflight: disk space (>=500 MB)
:: ---------------------------------------------------------------------------
:preflight_disk
call :log_info "Preflight: checking disk space (>= !MIN_DISK_MB! MB)..."
for /f "tokens=3" %%F in ('dir /-c "!SCRIPT_DIR!" ^| findstr /i "bytes free" 2^>nul') do (
    set "BYTES_FREE=%%F"
)
:: Remove commas from number
set "BYTES_FREE=!BYTES_FREE:,=!"
if not defined BYTES_FREE (
    call :log_warn "Could not determine free disk space — skipping check."
    goto :eof
)
:: Convert bytes -> MB  (approximate, use integer division trick)
set /a "MB_FREE=!BYTES_FREE:~0,-6!" 2>nul || set "MB_FREE=9999"
if !MB_FREE! LSS !MIN_DISK_MB! (
    call :log_error "Insufficient disk: !MB_FREE! MB free, need !MIN_DISK_MB! MB."
    exit /b 1
)
call :log_ok "Disk space OK: ~!MB_FREE! MB free."
goto :eof

:: ---------------------------------------------------------------------------
:: Handle --reinstall
:: ---------------------------------------------------------------------------
:handle_reinstall
call :log_warn "--reinstall: removing existing venv (!VENV_DIR!)..."
if !DRY_RUN! equ 1 (
    call :log_dry "Would remove: !VENV_DIR!"
) else (
    if exist "!VENV_DIR!" rmdir /s /q "!VENV_DIR!" 2>nul
)

if exist "dashboard\sylion.db" (
    set "DB_BAK=dashboard\sylion.db.bak.v!SCRIPT_VERSION!_%TIMESTAMP%"
    if not defined TIMESTAMP (
        for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "DATESTAMP=%%c%%a%%b"
        for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "TIMESTAMP=!DATESTAMP!_%%a%%b"
    )
    set "DB_BAK=dashboard\sylion.db.bak.v!SCRIPT_VERSION!_!TIMESTAMP!"
    call :log_warn "--reinstall: backing up DB to !DB_BAK!"
    if !DRY_RUN! equ 1 (
        call :log_dry "Would copy dashboard\sylion.db to !DB_BAK!"
    ) else (
        copy /y "dashboard\sylion.db" "!DB_BAK!" >nul
        del /f /q "dashboard\sylion.db" 2>nul
        call :log_ok "DB backed up to: !DB_BAK!"
    )
)
goto :eof

:: ---------------------------------------------------------------------------
:: Step 1: Create virtual environment (idempotent)
:: ---------------------------------------------------------------------------
:create_venv
call :log_info "Setting up virtual environment at: !VENV_DIR!"

if !DRY_RUN! equ 1 (
    call :log_dry "Would create venv at !VENV_DIR! with !PYTHON_BIN!"
    goto :eof
)

if exist "!VENV_DIR!\Scripts\python.exe" (
    "!VENV_PYTHON!" -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        call :log_ok "Venv already exists and is functional -- skipping."
        goto :eof
    ) else (
        call :log_warn "Existing venv appears broken. Recreating..."
        rmdir /s /q "!VENV_DIR!" 2>nul
    )
)

set "VENV_CREATED=1"
!PYTHON_BIN! -m venv "!VENV_DIR!"
if !errorlevel! neq 0 (
    call :log_error "Failed to create virtual environment."
    exit /b 1
)
call :log_ok "Virtual environment created."
goto :eof

:: ---------------------------------------------------------------------------
:: Step 2: Install dependencies (hash-verified, with fallback)
:: ---------------------------------------------------------------------------
:install_deps
call :log_info "Installing dependencies from !REQ_FILE!..."

if not exist "!REQ_FILE!" (
    call :log_error "Requirements file not found: !REQ_FILE!"
    exit /b 1
)

if !DRY_RUN! equ 1 (
    call :log_dry "Would run: pip install --require-hashes -r !REQ_FILE!"
    goto :eof
)

"!VENV_PIP!" install --quiet --upgrade pip
if !errorlevel! neq 0 call :log_warn "pip upgrade failed -- continuing."

:: Check if lockfile contains hashes
findstr /c:"sha256:" "!REQ_FILE!" >nul 2>&1
if !errorlevel! equ 0 (
    call :log_info "Hash verification mode (--require-hashes) enabled."
    "!VENV_PIP!" install --quiet --require-hashes --no-cache-dir -r "!REQ_FILE!" 2>nul
    if !errorlevel! neq 0 (
        call :log_error "Dependency install failed (hash mismatch or network error)."
        exit /b 1
    )
) else (
    call :log_warn "No sha256 hashes in !REQ_FILE! -- installing without hash verification."
    call :log_warn "Run pip-compile --generate-hashes to add hashes for security."
    "!VENV_PIP!" install --quiet --no-cache-dir -r "!REQ_FILE!"
    if !errorlevel! neq 0 (
        call :log_error "Dependency installation failed."
        exit /b 1
    )
)

call :log_ok "Dependencies installed."
goto :eof

:: ---------------------------------------------------------------------------
:: Step 3: Initialize runtime database placeholder
:: ---------------------------------------------------------------------------
:init_database
call :log_info "Preparing unified runtime database path..."

if !DRY_RUN! equ 1 (
    call :log_dry "Would prepare runtime database path"
    goto :eof
)

if not defined SYLION_DB_PATH set "SYLION_DB_PATH=%USERPROFILE%\sylion\sylion_aeis.db"
for %%D in ("!SYLION_DB_PATH!") do if not exist "%%~dpD" mkdir "%%~dpD" 2>nul
if not exist "!SYLION_DB_PATH!" type nul > "!SYLION_DB_PATH!"

call :log_ok "Runtime database path ready: !SYLION_DB_PATH!"
goto :eof

:: ---------------------------------------------------------------------------
:: Step 4: Generate SETUP_TOKEN.txt (idempotent)
:: ---------------------------------------------------------------------------
:generate_token
call :log_info "Generating setup token..."

if !DRY_RUN! equ 1 (
    call :log_dry "Would write token to !SETUP_TOKEN_FILE!"
    goto :eof
)

if exist "!SETUP_TOKEN_FILE!" (
    call :log_ok "SETUP_TOKEN.txt already exists -- skipping regeneration."
    goto :eof
)

for /f "tokens=*" %%T in ('"!VENV_PYTHON!" -c "import secrets; print(secrets.token_urlsafe(32))"') do (
    set "SETUP_TOKEN=%%T"
)

if not defined SETUP_TOKEN (
    call :log_warn "Could not generate token -- writing placeholder."
    set "SETUP_TOKEN=CHANGE_ME_BEFORE_FIRST_LOGIN"
)

(
    echo # SYLION v!SCRIPT_VERSION! -- Setup Token
    echo # Generated: %DATE% %TIME%
    echo # Use at http://127.0.0.1:!SYLION_PORT!/setup
    echo # DELETE or rotate this file after first login.
    echo SETUP_TOKEN=!SETUP_TOKEN!
) > "!SETUP_TOKEN_FILE!"

:: Windows: restrict to current user via icacls
icacls "!SETUP_TOKEN_FILE!" /inheritance:r /grant:r "%USERNAME%":F >nul 2>&1

call :log_ok "SETUP_TOKEN.txt created. Token: !SETUP_TOKEN!"
goto :eof

:: ---------------------------------------------------------------------------
:: Step 5: Seed agents from agents.yaml (idempotent via upsert)
:: ---------------------------------------------------------------------------
:seed_agents
call :log_info "Seeding agents from !AGENTS_YAML!..."

if !DRY_RUN! equ 1 (
    call :log_dry "Would skip legacy dashboard agent seeding"
    goto :eof
)

if not exist "!AGENTS_YAML!" (
    call :log_warn "agents.yaml not found -- skipping agent seeding."
    goto :eof
)

call :log_warn "Legacy dashboard agent seeding removed in R3.13; unified runtime bootstraps agents separately."

call :log_ok "Agent seeding step complete."
goto :eof

:: ---------------------------------------------------------------------------
:: Step 6: Healthcheck (non-fatal; tries curl.exe then PowerShell)
:: ---------------------------------------------------------------------------
:healthcheck
call :log_info "Healthcheck: !HEALTH_URL! (5 attempts, 3s apart)..."

if !DRY_RUN! equ 1 (
    call :log_dry "Would poll: !HEALTH_URL!"
    goto :eof
)

set "HC_PASSED=0"

where curl.exe >nul 2>&1
if !errorlevel! equ 0 (
    for /L %%i in (1,1,5) do (
        if !HC_PASSED! equ 0 (
            curl.exe -sf -o nul -w "%%{http_code}" "!HEALTH_URL!" > "%TEMP%\sylion_hc.txt" 2>nul
            set /p HC_CODE=<"%TEMP%\sylion_hc.txt"
            if "!HC_CODE!"=="200" (
                call :log_ok "Healthcheck passed (HTTP 200) via curl.exe."
                set "HC_PASSED=1"
            ) else (
                call :log_warn "Attempt %%i/5: HTTP !HC_CODE! -- retrying in 3s..."
                timeout /t 3 /nobreak >nul
            )
        )
    )
) else (
    for /L %%i in (1,1,5) do (
        if !HC_PASSED! equ 0 (
            powershell -NoProfile -NonInteractive -Command ^
                "try { $r = Invoke-WebRequest -Uri '!HEALTH_URL!' -UseBasicParsing -TimeoutSec 5; Write-Output $r.StatusCode } catch { Write-Output 0 }" ^
                > "%TEMP%\sylion_hc.txt" 2>nul
            set /p HC_CODE=<"%TEMP%\sylion_hc.txt"
            if "!HC_CODE!"=="200" (
                call :log_ok "Healthcheck passed (HTTP 200) via PowerShell."
                set "HC_PASSED=1"
            ) else (
                call :log_warn "Attempt %%i/5: status !HC_CODE! -- retrying in 3s..."
                timeout /t 3 /nobreak >nul
            )
        )
    )
)

if !HC_PASSED! equ 0 (
    call :log_warn "Healthcheck not passed -- server may not be running yet."
)
goto :eof

:: ---------------------------------------------------------------------------
:: Print next steps
:: ---------------------------------------------------------------------------
:print_next_steps
echo.
echo ============================================================
call :log_ok "SYLION v!SCRIPT_VERSION! installation complete."
if !DRY_RUN! equ 1 echo [DRY-RUN] No changes were made.
echo.
echo   NEXT STEPS:
echo   1. Activate:  !VENV_DIR!\Scripts\activate
echo   2. Start:     python -m sylion.server --host 127.0.0.1 --http-port !SYLION_PORT!
echo   3. Health:    !HEALTH_URL!
if exist "!SETUP_TOKEN_FILE!" (
    echo   4. Setup URL: http://127.0.0.1:!SYLION_PORT!/setup
    echo      Token file: !SETUP_TOKEN_FILE! -- delete after first login.
)
echo.
echo   Log file:  !SYLION_LOG!
echo ============================================================
echo.
goto :eof

:: ---------------------------------------------------------------------------
:: Done (success)
:: ---------------------------------------------------------------------------
:done
endlocal
exit /b 0

:: ---------------------------------------------------------------------------
:: Failure handler (rollback partial venv)
:: ---------------------------------------------------------------------------
:fail
set "INSTALL_FAILED=1"
call :log_error "Installation FAILED. See log: !SYLION_LOG!"
if !VENV_CREATED! equ 1 (
    call :log_warn "Rolling back: removing partial venv (!VENV_DIR!)..."
    rmdir /s /q "!VENV_DIR!" 2>nul
    call :log_warn "Venv rollback complete."
)
echo.
endlocal
exit /b 1

:: ---------------------------------------------------------------------------
:: Logging helpers
:: Cmd.exe has no ANSI colors by default; PowerShell write is too slow.
:: We use VT100 if the terminal supports it (Windows 10 1511+).
:: ---------------------------------------------------------------------------
:log_info
echo [INFO]  %~1
if !DRY_RUN! equ 0 if defined SYLION_LOG echo [INFO]  %~1 >> "!SYLION_LOG!" 2>nul
goto :eof

:log_ok
echo [OK]    %~1
if !DRY_RUN! equ 0 if defined SYLION_LOG echo [OK]    %~1 >> "!SYLION_LOG!" 2>nul
goto :eof

:log_warn
echo [WARN]  %~1
if !DRY_RUN! equ 0 if defined SYLION_LOG echo [WARN]  %~1 >> "!SYLION_LOG!" 2>nul
goto :eof

:log_error
echo [ERROR] %~1
if !DRY_RUN! equ 0 if defined SYLION_LOG echo [ERROR] %~1 >> "!SYLION_LOG!" 2>nul
goto :eof

:log_dry
echo [DRY]   %~1
goto :eof
