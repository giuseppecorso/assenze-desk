@echo off
rem Toglie Assenze Desk e i suoi collegamenti. I dati in %LOCALAPPDATA%\AssenzeDesk
rem (archivio, impostazioni, certificati) restano: si cancellano a mano, se servisse.
chcp 65001 >nul
setlocal
title Disinstallazione di Assenze Desk
set "DESTINAZIONE=%LOCALAPPDATA%\Programs\AssenzeDesk"

tasklist /fi "imagename eq AssenzeDesk.exe" 2>nul | find /i "AssenzeDesk.exe" >nul
if not errorlevel 1 (
    echo Assenze Desk è aperto: chiudilo, poi apri di nuovo Disinstalla.cmd.
    pause
    exit /b 1
)
choice /c SN /m "Vuoi togliere Assenze Desk da questo PC? I dati restano"
if errorlevel 2 exit /b 0

powershell -NoProfile -Command "foreach ($c in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { Remove-Item -LiteralPath (Join-Path $c 'Assenze Desk.lnk') -ErrorAction SilentlyContinue }"
echo Assenze Desk è stato tolto. I dati restano in %LOCALAPPDATA%\AssenzeDesk.
pause
cd /d "%TEMP%"
(goto) 2>nul & rmdir /s /q "%DESTINAZIONE%"
