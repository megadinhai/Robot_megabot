@echo off
chcp 65001 >nul
echo ========================================================
echo       TOOL NAP FIRMWARE OTTO ROBOT (VIETNAMESE EDITION)
echo   Giao diện: Web Admin :8080 ^| Màn hình OLED xoay Ngang
echo   Server: robot-megabot.onrender.com ^& xiaozhi.me
echo ========================================================
echo.

set /p COMPORT="Nhập cổng COM của Robot (ví dụ: COM3, COM8, COM5) [Mặc định COM3]: "
if "%COMPORT%"=="" set COMPORT=COM3

echo.
echo Đang chuẩn bị nạp file: otto_megabot_all_in_one_0x0.bin vào %COMPORT%...
echo Tốc độ nạp: 460800 baud
echo.

REM Tìm python với esptool
set ESPTOOL_CMD=python -m esptool
%ESPTOOL_CMD% version >nul 2>&1
if %errorlevel% neq 0 (
    if exist "C:\Users\%USERNAME%\.espressif\python_env\idf6.1_py3.14_env\Scripts\python.exe" (
        set ESPTOOL_CMD=C:\Users\%USERNAME%\.espressif\python_env\idf6.1_py3.14_env\Scripts\python.exe -m esptool
    ) else if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe" (
        set ESPTOOL_CMD=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe -m esptool
    )
)

echo Đang thực hiện nạp firmware toàn diện từ địa chỉ 0x0...
%ESPTOOL_CMD% --chip esp32s3 -p %COMPORT% -b 460800 --before default-reset --after hard-reset write_flash --flash_mode dio --flash_size 16MB --flash_freq 80m 0x0 otto_megabot_all_in_one_0x0.bin

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo [THÀNH CÔNG] Đã nạp xong firmware Otto Robot trên %COMPORT%!
    echo Robot đang khởi động lại...
    echo.
    echo 1. TRUY CẬP WEB ADMIN QUẢN TRỊ ROBOT:
    echo    Khi kết nối WiFi phát từ robot (Megabot_AP):
    echo      http://192.168.4.1:8080
    echo    Khi robot đã vào mạng WiFi nhà bạn:
    echo      http://^<IP-ROBOT^>:8080
    echo.
    echo 2. ĐỔI SERVER TRÊN WEB ADMIN:
    echo    Vào mục 'Cài đặt Server AI':
    echo    - Megabot Render: wss://robot-megabot.onrender.com/ws/megabot
    echo    - XiaoZhi Gốc: wss://api.xiaozhi.me/v1/cc
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo [LỖI] Không thể nạp vào %COMPORT%. Vui lòng kiểm tra:
    echo 1. Cổng %COMPORT% đã đúng chưa?
    echo 2. Hãy đóng các phần mềm đang chiếm cổng COM (Serial Monitor, v.v.).
    echo 3. Nhấn giữ nút BOOT trên mạch rồi cắm cáp USB để vào chế độ Download.
    echo ========================================================
)

pause
