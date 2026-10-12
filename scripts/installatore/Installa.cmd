@echo off
rem Installa Assenze Desk per l'utente corrente, senza permessi di amministratore:
rem copia la cartella in %LOCALAPPDATA%\Programs\AssenzeDesk e crea i collegamenti
rem sul Desktop e nel menu Start. I dati (archivio e impostazioni) non si toccano.
chcp 65001 >nul
setlocal
title Installazione di Assenze Desk
set "SORGENTE=%~dp0"
set "DESTINAZIONE=%LOCALAPPDATA%\Programs\AssenzeDesk"

if not exist "%SORGENTE%AssenzeDesk.exe" (
    echo Non trovo AssenzeDesk.exe accanto a questo file.
    echo Estrai prima tutto lo zip: tasto destro sullo zip, "Estrai tutto",
    echo poi apri Installa.cmd dalla cartella estratta.
    goto fine
)
if /i "%SORGENTE%"=="%DESTINAZIONE%\" (
    echo Assenze Desk è già installato in questa cartella.
    goto fine
)
tasklist /fi "imagename eq AssenzeDesk.exe" 2>nul | find /i "AssenzeDesk.exe" >nul
if not errorlevel 1 (
    echo Assenze Desk è aperto: chiudilo, poi apri di nuovo Installa.cmd.
    goto fine
)

echo Copio Assenze Desk in %DESTINAZIONE% ...
robocopy "%SORGENTE%." "%DESTINAZIONE%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo Copia non riuscita: controlla lo spazio libero e riprova.
    goto fine
)

echo Creo l'icona sul Desktop e nel menu Start ...
powershell -NoProfile -Command "$d = $env:DESTINAZIONE; Get-ChildItem -LiteralPath $d -Recurse -File | Unblock-File; $s = New-Object -ComObject WScript.Shell; foreach ($c in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { $l = $s.CreateShortcut((Join-Path $c 'Assenze Desk.lnk')); $l.TargetPath = (Join-Path $d 'AssenzeDesk.exe'); $l.WorkingDirectory = $d; $l.IconLocation = (Join-Path $d 'AssenzeDesk.exe') + ',0'; $l.Description = 'Assenze Desk'; $l.Save() }"
if errorlevel 1 (
    echo Non sono riuscito a creare l'icona. L'app è installata comunque:
    echo apri %DESTINAZIONE%, tasto destro su AssenzeDesk.exe, "Mostra altre opzioni",
    echo "Invia a", "Desktop (crea collegamento)".
    goto fine
)

echo.
echo Fatto. Assenze Desk si apre dall'icona "Assenze Desk" sul Desktop.
echo Per aggiornarlo in futuro: estrai il nuovo zip e apri di nuovo Installa.cmd.
echo Per toglierlo: Disinstalla.cmd nella cartella %DESTINAZIONE%.
start "" "%DESTINAZIONE%\AssenzeDesk.exe"

:fine
echo.
pause
