@echo off
where ollama >nul 2>&1
if errorlevel 1 goto missing
ollama list >nul 2>&1
if errorlevel 1 start "Ollama" ollama serve
timeout /t 3 /nobreak >nul
ollama pull qwen3.5:9b
if errorlevel 1 echo Download fejlede. Se fejlen ovenfor.
pause
exit /b
:missing
echo Installer Ollama fra https://ollama.com/download/windows og prov igen.
pause
