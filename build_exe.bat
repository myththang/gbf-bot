@echo off
title Dong goi GBF Bot thanh file EXE
cd /d "%~dp0"

echo ===================================================
echo   DONG GOI GBF BOT THANH FILE EXE TUY CHINH
echo ===================================================
echo.

:: 1. Kiem tra/Cai dat PyInstaller va cac thu vien phu thuoc
echo [1/4] Dang kiem tra cac thu vien can thiet...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [WARNING] Python hoac launcher 'py' chua duoc cai dat!
        pause
        exit /b 1
    ) else (
        set PY_CMD=py
    )
) else (
    set PY_CMD=python
)

%PY_CMD% -m pip install pyinstaller PySide6 opencv-python numpy Pillow adbutils --upgrade --quiet
if %errorlevel% neq 0 (
    echo [WARNING] Co loi khi chay pip install. Vui long dam bao ban da cai dat Python va pip!
)

:: 2. Xoa cac thu muc build cu neu co
echo.
echo [2/4] Dang don dep cac ban build cu...

:: Tat adb.exe de giai phong file lock (hoan toan an toan va khong lam crash CMD)
taskkill /f /im adb.exe >nul 2>&1

:: Co gang xoa thu muc build cu
if exist "dist\GBF_Bot" (
    echo Dang xoa thu muc cu 'dist\GBF_Bot'...
    rmdir /s /q "dist\GBF_Bot" >nul 2>&1
    
    :: Thu lai lan 2 voi do tre phong tru truong hop Windows dang lock tam thoi
    if exist "dist\GBF_Bot" (
        ping 127.0.0.1 -n 3 >nul
        rmdir /s /q "dist\GBF_Bot" >nul 2>&1
    )
    
    :: Neu van khong the xoa, huong dan nguoi dung tat cac tien trinh gay khoa file
    if exist "dist\GBF_Bot" (
        echo.
        echo [ERROR] Khong the xoa thu muc 'dist\GBF_Bot' vi co file dang bi khoa!
        echo.
        echo HUONG DAN SUA LOI NHANH:
        echo ---------------------------------------------------
        echo 1. Neu ban dang mo ung dung GBF_Bot.exe, hay tat no di.
        echo 2. Tat cac tab CMD hoac File Explorer dang mo thu muc GBF_Bot.
        echo 3. Nhap vao o tim kiem cua Resource Monitor de tat tien trinh 'adb.exe' hoac 'pythonw.exe'.
        echo.
        echo * Sau khi lam cac buoc tren, ban hay chay lai file build nay.
        echo ---------------------------------------------------
        pause
        exit /b 1
    )
)
if exist build rmdir /s /q build
if exist "GBF_Bot.spec" del /q "GBF_Bot.spec"

:: 3. Chuyen doi logo.png thanh logo.ico neu co
echo.
echo [3/4] Dang kiem tra va khoi tao file icon...
if exist "logo.png" (
    echo [INFO] Phat hien logo.png, dang tao logo.ico...
    %PY_CMD% -c "from PIL import Image; Image.open('logo.png').save('logo.ico', format='ICO')" >nul 2>&1
)

:: 4. Build voi PyInstaller
echo.
echo [4/4] Dang chay PyInstaller de tao file EXE...
echo Chu y: Qua trinh nay co the mat tu 1-3 phut tuy thuoc vao may cua ban.
echo.

:: Chay PyInstaller tuy thuoc vao viec co icon hay khong de tranh loi bien moi truong
if exist "logo.ico" (
    %PY_CMD% -m PyInstaller --noconsole --name="GBF_Bot" --icon=logo.ico --noconfirm --clean gbf_gui.py
) else (
    %PY_CMD% -m PyInstaller --noconsole --name="GBF_Bot" --noconfirm --clean gbf_gui.py
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build that bai! Vui long kiem tra thong tin loi o tren.
    pause
    exit /b 1
)

:: 5. Chep cac thu muc va file cau hinh vao thu muc build
echo.
echo ===================================================
echo   THIET LAP THU MUC OUTPUT
echo ===================================================
echo.

if exist "dist\GBF_Bot" (
    echo [INFO] Copy thu muc assets vao thu muc cua file EXE...
    xcopy /E /I /Y "assets" "dist\GBF_Bot\assets" >nul
    
    if exist "logo.png" (
        echo [INFO] Copy file logo.png cho giao dien...
        copy /Y "logo.png" "dist\GBF_Bot\" >nul
    )
    
    if exist "config.txt" (
        echo [INFO] Copy file config.txt...
        copy /Y "config.txt" "dist\GBF_Bot\" >nul
    )
    
    echo.
    echo ===================================================
    echo  BUILD THANH CONG!
    echo ===================================================
    echo  Thu muc chua file EXE: %~dp0dist\GBF_Bot
    echo  File chay chinh: GBF_Bot.exe (Nhan dup vao de chay)
    echo.
    echo  * Ban co the copy ca thu muc "GBF_Bot" nay di bat ky dau de chay.
    echo ===================================================
) else (
    echo [WARNING] Khong tim thay thu muc dist\GBF_Bot. Vui long kiem tra lai.
)

pause
