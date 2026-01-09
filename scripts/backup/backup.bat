@echo off
REM Neo4j Backup Windows Batch Script
REM
REM Usage:
REM   backup.bat              - Full backup
REM   backup.bat --incremental - Incremental backup
REM
REM Schedule with Windows Task Scheduler

setlocal

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..\..\
set BACKUP_DIR=%PROJECT_ROOT%backups\neo4j

REM Create backup directory if it doesn't exist
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo ==========================================
echo Forge Neo4j Backup
echo Date: %date% %time%
echo ==========================================

REM Change to project directory
cd /d "%PROJECT_ROOT%forge-cascade-v2"

REM Check for Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Python not found in PATH
    exit /b 1
)

REM Run backup script
python "%SCRIPT_DIR%neo4j_backup.py" --backup-dir "%BACKUP_DIR%" %*

if %ERRORLEVEL% equ 0 (
    echo Backup completed successfully
) else (
    echo Backup failed with exit code %ERRORLEVEL%
)

exit /b %ERRORLEVEL%
