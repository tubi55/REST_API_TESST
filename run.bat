@echo off

chcp 65001 > nul
cd /d "%~dp0"

python -c "import os,sys;from app.core.config import DB_PATH;print(DB_PATH);sys.exit(0 if os.path.exists(DB_PATH) else 1)"
if errorlevel 1 (
    echo   ^^ this DB does not exist yet - building it from data\*.csv
    python -m pipeline schema
    if errorlevel 1 goto fail
    python -m pipeline chunk
    if errorlevel 1 goto fail
    python -m pipeline embed
    if errorlevel 1 goto fail
    python -m pipeline verify
    if errorlevel 1 goto fail
)

echo.
echo   API    http://127.0.0.1:8000/docs      token: dev-token (Authorization: Bearer)
echo   SCREEN cd web ^&^& python -m http.server 3000   then open http://localhost:3000
echo.
echo   Use 127.0.0.1, not localhost: localhost tries IPv6 (::1) first and the
echo   refused connect costs ~2 seconds per request on Windows.
echo   Ctrl+C to stop
echo.
python -m uvicorn app.main:app --reload
goto end

:fail
echo.
echo   Pipeline failed. Read the message above.
echo   Most common cause: the server is still running and holding cosmetic.db.
pause

:end
