@echo off
REM Media Library Organization (Standalone)
REM Requires Docker Desktop with Model Runner enabled

if not defined MEDIA_PATH set MEDIA_PATH=C:\Users\TiHa\Data\DOWNLOADS\_Download_Extrects
cd /d %~dp0

echo Media Library Organization
echo ==========================
echo.
echo MEDIA_PATH=%MEDIA_PATH%
echo Running in Docker container...
docker-compose up --abort-on-container-exit media-organizer

pause
