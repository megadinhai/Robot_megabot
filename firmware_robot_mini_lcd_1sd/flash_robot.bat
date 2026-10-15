@echo off
chcp 65001 >nul
echo ========================================================
echo       TOOL NAP FIRMWARE MEGABOT (ROBOT-MINI-LCD-1SD)
echo   Tich hop: Web Admin Doi Chan GPIO, Motor Calib & MCP
echo ========================================================
echo.

set /p COMPORT="Nhap cong COM cua Robot (vi du: COM8, COM3, COM5): "
if "%COMPORT%"=="" (
    echo Khong duoc de trong cong COM!
    pause
    exit /b
)

echo.
echo Dang chuan bi nap file: robot-mini-lcd-1sd-merged-all-in-one-0x0.bin vao %COMPORT%...
echo Toc do nap: 460800 baud
echo.

REM Thu tim python voi esptool
set ESPTOOL_CMD=python -m esptool
%ESPTOOL_CMD% version >nul 2>&1
if %errorlevel% neq 0 (
    set ESPTOOL_CMD=C:\Users\%USERNAME%\.espressif\python_env\idf6.1_py3.14_env\Scripts\python.exe -m esptool
)

echo Thuc hien nap firmware toan dien...
%ESPTOOL_CMD% --chip esp32s3 -p %COMPORT% -b 460800 --before default-reset --after hard-reset write-flash --flash-mode dio --flash-size 16MB --flash-freq 80m 0x0 robot-mini-lcd-1sd-merged-all-in-one-0x0.bin

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo [THANH CONG] Da nap xong firmware cho Robot tren %COMPORT%!
    echo Robot dang khoi dong lai...
    echo.
    echo TRUY CAP WEB ADMIN CAI DAT CHAN GPIO:
    echo Khi ket noi WiFi robot hoac robot cung mang WiFi:
    echo   http://^<IP-CUA-ROBOT^>:8080
    echo   Hoac che do AP: http://192.168.4.1:8080
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo [LOI] Khong the nap vao %COMPORT%. Vui long kiem tra:
    echo 1. Dung cong COM chua?
    echo 2. Co phan mem nao khac dang mo COM nay khong?
    echo 3. Bam giu nut BOOT roi cam cap lai de vao che do Download.
    echo ========================================================
)

pause
