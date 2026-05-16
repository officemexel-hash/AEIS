@echo off
REM Start SYLION Pipeline v6.2.0 dev server (Windows CMD)
setlocal enabledelayedexpansion

set "INSTALL_DIR=%cd%"
set "SRC_DIR=%INSTALL_DIR%\src\sylion-pipeline"
set "VENV_DIR=%INSTALL_DIR%\.venv"
set "ENV_FILE=%INSTALL_DIR%\.env.generated"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
  echo [ERROR] venv nie istnieje. Uruchom najpierw: scripts\install.bat
  exit /b 1
)
if not exist "%ENV_FILE%" (
  echo [ERROR] .env.generated nie istnieje. Uruchom najpierw: scripts\install.bat
  exit /b 1
)

REM Load env vars from .env.generated, pomijajac komentarze i puste linie
for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
  set "_KEY=%%A"
  set "_VAL=%%B"
  if not "!_KEY!"=="" (
    set "_FIRST=!_KEY:~0,1!"
    if not "!_FIRST!"=="#" (
      set "!_KEY!=!_VAL!"
    )
  )
)

set "SYLION_USE_LEGACY_DB_PATH=0"
set "SESSION_COOKIE_SECURE=0"
set "SYLION_ENV=dev"
set "SYLION_AEIS_ENV=dev"
set "SYLION_RBAC_DISABLED=1"
set "SYLION_RATE_LIMIT_DISABLED=1"
set "SYLION_AUTH_BYPASS=1"
set "PYTHONPATH=%SRC_DIR%"
set "LITELLM_LOCAL_MODEL_COST_MAP=True"
set "LITELLM_DO_NOT_TRACK=True"

call "%VENV_DIR%\Scripts\activate.bat"
cd /d "%SRC_DIR%"

echo.
echo Serwer SYLION AEIS API startuje na http://127.0.0.1:8010
echo Zatrzymanie: Ctrl+C (graceful shutdown do 10s)
echo.

python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010 --timeout-graceful-shutdown 10

endlocal
