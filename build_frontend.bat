@echo off
echo ========================================
echo I.R.I.S. React Frontend Build
echo ========================================
echo.

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js ist nicht installiert oder nicht im PATH.
    echo Bitte installieren Sie Node.js von https://nodejs.org
    pause
    exit /b 1
)

echo Node.js gefunden. Baue React Frontend...
echo.

REM Navigate to React frontend directory
cd frontend

REM Install dependencies if node_modules doesn't exist
if not exist "node_modules" (
    echo Installiere Abhängigkeiten...
    npm install
    if errorlevel 1 (
        echo ERROR: Installation der Abhängigkeiten fehlgeschlagen.
        pause
        exit /b 1
    )
) else (
    echo Abhängigkeiten bereits installiert.
)

echo.
echo Baue Production Build...
npm run build
if errorlevel 1 (
    echo ERROR: Build fehlgeschlagen.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build erfolgreich abgeschlossen!
echo ========================================
echo.
echo Das React Frontend wurde in frontend/dist/ erstellt.
echo Sie können nun den Server mit 'python src/start.py' starten.
echo.
echo Frontend verfügbar unter: http://localhost:8000
echo Upscaler verfügbar unter: http://localhost:8000/upscaler
echo.
pause