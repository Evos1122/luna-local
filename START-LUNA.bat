@echo off
setlocal
cd /d "%~dp0"

rem --- 1) Ollama foerst. Den startes i baggrunden, saa intet blokerer. ---
where ollama >nul 2>&1
if errorlevel 1 goto noollama
ollama list >nul 2>&1
if not errorlevel 1 goto ollamaok
echo Starter Ollama i baggrunden...
start "Ollama" /min ollama serve
set /a waitcount=0
:waitollama
ping -n 2 127.0.0.1 >nul
ollama list >nul 2>&1
if not errorlevel 1 goto ollamaok
set /a waitcount+=1
if %waitcount% lss 30 goto waitollama
goto noollama

:ollamaok
rem --- 2) Luna ---
where py >nul 2>&1
if errorlevel 1 goto python
start "Luna Local" py -3 server.py
goto browser
:python
where python >nul 2>&1
if errorlevel 1 goto missing
start "Luna Local" python server.py

:browser
rem Venter til serveren svarer, hoejst ca. 10 sekunder, foer browseren aabnes.
where curl >nul 2>&1
if errorlevel 1 (
  ping -n 3 127.0.0.1 >nul
  goto open
)
set /a waitcount=0
:waitluna
curl -s -o nul -f http://127.0.0.1:5000/api/status >nul 2>&1
if not errorlevel 1 goto open
ping -n 2 127.0.0.1 >nul
set /a waitcount+=1
if %waitcount% lss 10 goto waitluna

:open
start "" http://127.0.0.1:5000
exit /b

:noollama
echo Ollama svarer ikke, eller mangler paa denne maskine.
echo Koer manuelt i et terminalvindue:  ollama serve
echo (det vindue maa ikke lukkes - saa gaar Ollama ned igen)
echo Eller installer Ollama fra https://ollama.com/download/windows
pause
exit /b 1

:missing
echo Python mangler. Installer Python 3.10 eller nyere fra python.org.
pause
exit /b 1
