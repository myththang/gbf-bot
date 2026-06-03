# -*- coding: utf-8 -*-
"""
scan_templates.py
=================
Công cụ chụp lại ảnh mẫu (template) từ thiết bị Android qua ADB.
Cho phép bạn chọn vùng ROI thủ công trên ảnh chụp màn hình rồi lưu thành file .webp
để thay thế các ảnh cũ, giúp tăng confidence khi nhận diện.

Các ảnh cần scan trong bot:
  - assets/buttons/reload.webp
  - assets/buttons/ok.webp
  - assets/buttons/attack.webp
  - assets/buttons/full_auto.webp
  
(rocket.webp đã được scan lại lần trước, bỏ qua)

Cách dùng:
  python scan_templates.py
  
  -> Chương trình sẽ tự động chụp màn hình từ thiết bị,
     hiện cửa sổ OpenCV để bạn vẽ hộp chọn vùng (ROI),
     rồi lưu ảnh vào đúng đường dẫn thay thế ảnh cũ.
"""

import subprocess
import time
import os
import shutil
import cv2
import numpy as np
from PIL import Image
import io
import sys
import adbutils

# ==================== CẤU HÌNH ====================
DEVICE_ADDRESS = None  # Sẽ được tự động phát hiện qua auto_detect_device()

def auto_detect_device():
    """Tự động phát hiện thiết bị ADB đang online."""
    global DEVICE_ADDRESS
    try:
        devices = adbutils.adb.device_list()
        if not devices:
            return False
        DEVICE_ADDRESS = devices[0].serial
        print(f"[ADB] Tự động chọn thiết bị hoạt động: {DEVICE_ADDRESS}")
        return True
    except Exception as e:
        print(f"[ADB] Lỗi quét thiết bị qua adbutils: {e}")
        return False

# Danh sách các ảnh cần scan lại
# (tên hiển thị, đường dẫn file đích, gợi ý về nơi tìm element trên màn hình)
TEMPLATES_TO_SCAN = [
    {
        "name": "Attack Button",
        "path": "assets/buttons/attack.webp",
        "hint": "Tìm và kéo chọn vùng quanh NÚT ATTACK (nút đỏ lớn ở dưới màn hình chiến đấu)",
        "skipped": False,
    },
    {
        "name": "Full Auto Button",
        "path": "assets/buttons/full_auto.webp",
        "hint": "Tìm và kéo chọn vùng quanh CHỮ 'Full Auto' (nút toggle ở góc trên trái khu vực chiến đấu)",
        "skipped": False,
    },
    {
        "name": "OK Button",
        "path": "assets/buttons/ok.webp",
        "hint": "Tìm và kéo chọn vùng quanh NÚT OK (nút xác nhận trong hộp thoại)",
        "skipped": False,
    },
    {
        "name": "Reload Button",
        "path": "assets/buttons/reload.webp",
        "hint": "Tìm và kéo chọn vùng quanh BIỂU TƯỢNG TẢI LẠI TRANG (nút reload trên thanh trình duyệt)",
        "skipped": False,
    },
]


# ==================== ADB HELPER ====================
def get_adb_path():
    """Tự động tìm đường dẫn adb.exe."""
    system_adb = shutil.which("adb")
    if system_adb:
        return "adb"

    try:
        import site
        from pathlib import Path
        for site_pkg in site.getsitepackages():
            path = Path(site_pkg) / 'adbutils' / 'binaries' / 'adb.exe'
            if path.exists():
                return str(path)
    except Exception:
        pass

    common_paths = [
        r"C:\LDPlayer\LDPlayer9\adb.exe",
        r"C:\LDPlayer\LDPlayer4\adb.exe",
        r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
        r"C:\Program Files\Netease\MuMuPlayer\shell\adb.exe",
        r"C:\Program Files\Nemu\vbox\adb.exe",
        r"C:\Program Files\Nox\bin\adb.exe",
        r"C:\Program Files (x86)\Nox\bin\adb.exe",
        r"C:\Program Files\Microvirt\MEmu\adb.exe",
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path
    return "adb"


def run_adb(command):
    """Thực thi lệnh ADB và trả về output dạng bytes hoặc string."""
    adb_path = get_adb_path()
    full_cmd = [adb_path]
    if DEVICE_ADDRESS:
        full_cmd.extend(['-s', DEVICE_ADDRESS])
    full_cmd.extend(command)

    try:
        if 'screencap' in command:
            result = subprocess.run(full_cmd, capture_output=True, check=True, shell=True)
            return result.stdout
        else:
            result = subprocess.run(full_cmd, capture_output=True, text=True, check=True, shell=True)
            return result.stdout.strip()
    except Exception as e:
        print(f"[ADB ERROR] {e}")
        return None


def take_screenshot():
    """Chụp màn hình qua ADB, trả về ảnh dạng numpy array (BGR cho OpenCV)."""
    print("[ADB] Đang chụp màn hình thiết bị...")
    raw_data = run_adb(['shell', 'screencap', '-p'])
    if not raw_data:
        raise RuntimeError("Không thể chụp màn hình từ thiết bị. Kiểm tra kết nối ADB!")

    # Sửa lỗi line ending trên Windows
    if os.name == 'nt':
        raw_data = raw_data.replace(b'\r\n', b'\n')

    nparr = np.frombuffer(raw_data, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        # Fallback dùng PIL
        pil_img = Image.open(io.BytesIO(raw_data)).convert("RGB")
        img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    return img_bgr


# ==================== HIỂN THỊ & CHỌN VÙNG ROI ====================
# Biến toàn cục cho callback chuột
_drawing = False
_roi_start = (-1, -1)
_roi_end = (-1, -1)
_roi_done = False
_img_display = None  # Bản sao để vẽ hộp preview lên


def _mouse_callback(event, x, y, flags, param):
    """Callback xử lý sự kiện chuột trong cửa sổ OpenCV."""
    global _drawing, _roi_start, _roi_end, _roi_done, _img_display

    if event == cv2.EVENT_LBUTTONDOWN:
        _drawing = True
        _roi_start = (x, y)
        _roi_end = (x, y)
        _roi_done = False

    elif event == cv2.EVENT_MOUSEMOVE:
        if _drawing:
            _roi_end = (x, y)
            # Vẽ preview hộp chọn
            _img_display = param.copy()
            cv2.rectangle(_img_display, _roi_start, _roi_end, (0, 255, 0), 2)
            cv2.imshow("Scan Template Tool", _img_display)

    elif event == cv2.EVENT_LBUTTONUP:
        _drawing = False
        _roi_end = (x, y)
        _roi_done = True
        # Vẽ hộp chọn cuối cùng
        _img_display = param.copy()
        cv2.rectangle(_img_display, _roi_start, _roi_end, (0, 255, 0), 2)
        # Thêm nhãn xác nhận
        label = "Nhan ENTER de luu | R de chon lai | ESC de bo qua"
        cv2.putText(_img_display, label, (10, param.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1, cv2.LINE_AA)
        cv2.imshow("Scan Template Tool", _img_display)


def select_roi_interactive(screenshot_bgr, template_info):
    """
    Hiển thị cửa sổ để người dùng kéo chọn vùng ROI trên ảnh chụp màn hình.
    
    Returns:
        (x1, y1, x2, y2) nếu đã chọn, hoặc None nếu bỏ qua.
    """
    global _drawing, _roi_start, _roi_end, _roi_done, _img_display

    _drawing = False
    _roi_start = (-1, -1)
    _roi_end = (-1, -1)
    _roi_done = False

    # Scale ảnh xuống nếu quá lớn để vừa màn hình máy tính
    max_display_height = 900
    h, w = screenshot_bgr.shape[:2]
    scale = 1.0
    if h > max_display_height:
        scale = max_display_height / h
        display_img = cv2.resize(screenshot_bgr, (int(w * scale), int(h * scale)))
    else:
        display_img = screenshot_bgr.copy()

    _img_display = display_img.copy()

    # Vẽ tiêu đề và gợi ý lên ảnh
    overlay = _img_display.copy()
    cv2.rectangle(overlay, (0, 0), (display_img.shape[1], 60), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, _img_display, 0.4, 0, _img_display)

    title = f"[{template_info['name']}] {template_info['hint']}"
    cv2.putText(_img_display, title, (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(_img_display, "Keo chuot de chon vung | ENTER: luu | R: chon lai | S: bo qua anh nay | ESC: thoat",
                (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

    win_name = "Scan Template Tool"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, display_img.shape[1], display_img.shape[0])
    cv2.setMouseCallback(win_name, _mouse_callback, _img_display.copy())
    cv2.imshow(win_name, _img_display)

    while True:
        key = cv2.waitKey(30) & 0xFF

        if key == 13:  # ENTER
            if _roi_done and _roi_start != _roi_end:
                # Chuyển lại tọa độ gốc (bỏ scale)
                x1 = int(min(_roi_start[0], _roi_end[0]) / scale)
                y1 = int(min(_roi_start[1], _roi_end[1]) / scale)
                x2 = int(max(_roi_start[0], _roi_end[0]) / scale)
                y2 = int(max(_roi_start[1], _roi_end[1]) / scale)
                cv2.destroyWindow(win_name)
                return (x1, y1, x2, y2)
            else:
                print("[WARN] Chưa kéo chọn vùng nào! Hãy kéo chuột trước khi nhấn ENTER.")

        elif key == ord('r') or key == ord('R'):  # R: chọn lại
            _drawing = False
            _roi_done = False
            _img_display = display_img.copy()
            overlay2 = _img_display.copy()
            cv2.rectangle(overlay2, (0, 0), (display_img.shape[1], 60), (0, 0, 0), -1)
            cv2.addWeighted(overlay2, 0.6, _img_display, 0.4, 0, _img_display)
            cv2.putText(_img_display, title, (10, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(_img_display,
                        "Keo chuot de chon vung | ENTER: luu | R: chon lai | S: bo qua anh nay | ESC: thoat",
                        (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
            cv2.setMouseCallback(win_name, _mouse_callback, _img_display.copy())
            cv2.imshow(win_name, _img_display)
            print("[INFO] Đã reset. Kéo lại vùng chọn.")

        elif key == ord('s') or key == ord('S'):  # S: bỏ qua ảnh này
            cv2.destroyWindow(win_name)
            print(f"[SKIP] Bỏ qua '{template_info['name']}'.")
            return None

        elif key == 27:  # ESC: thoát toàn bộ
            cv2.destroyAllWindows()
            print("[EXIT] Người dùng thoát chương trình.")
            raise SystemExit

    cv2.destroyWindow(win_name)
    return None


# ==================== PREVIEW & XÁC NHẬN ====================
def preview_and_confirm(cropped_bgr, template_info):
    """
    Hiển thị preview ảnh đã crop để xác nhận trước khi lưu.
    
    Returns:
        True nếu xác nhận lưu, False nếu muốn chọn lại.
    """
    preview = cropped_bgr.copy()
    h, w = preview.shape[:2]

    # Phóng to ảnh nhỏ để dễ xem
    min_display = 300
    if h < min_display or w < min_display:
        scale = max(min_display / h, min_display / w)
        preview = cv2.resize(preview, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_NEAREST)

    # Thêm border
    preview = cv2.copyMakeBorder(preview, 10, 50, 10, 10,
                                  cv2.BORDER_CONSTANT, value=(30, 30, 30))
    cv2.putText(preview, "ENTER: Luu | R: Chon lai | S: Bo qua",
                (10, preview.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 100), 1, cv2.LINE_AA)

    win_name = f"Preview: {template_info['name']}"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.imshow(win_name, preview)

    print(f"\n[PREVIEW] Đây là ảnh sẽ được lưu cho '{template_info['name']}'")
    print("  -> Nhấn ENTER để lưu | R để chọn lại | S để bỏ qua ảnh này")

    while True:
        key = cv2.waitKey(0) & 0xFF
        cv2.destroyWindow(win_name)

        if key == 13:  # ENTER
            return True
        elif key == ord('r') or key == ord('R'):
            return False
        elif key == ord('s') or key == ord('S'):
            return None  # None = bỏ qua

    return False


# ==================== LƯU ẢNH ====================
def save_template(cropped_bgr, output_path):
    """Lưu ảnh crop thành file .webp với chất lượng cao."""
    # Tạo thư mục nếu chưa có
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Backup ảnh cũ
    if os.path.exists(output_path):
        backup_path = output_path.replace(".webp", f"_backup_{int(time.time())}.webp")
        import shutil as sh
        sh.copy2(output_path, backup_path)
        print(f"  [BACKUP] Ảnh cũ đã được backup tại: {backup_path}")

    # Lưu ảnh mới dạng webp (chất lượng 95)
    pil_img = Image.fromarray(cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2RGB))
    pil_img.save(output_path, format="WEBP", quality=95, method=6)
    print(f"  [SAVED] Ảnh mới đã được lưu tại: {output_path}")
    print(f"  [SIZE]  Kích thước ảnh: {pil_img.width} x {pil_img.height} px")


# ==================== KIỂM TRA CONFIDENCE ====================
def verify_confidence(screenshot_bgr, template_path, expected_min=0.75):
    """
    Sau khi lưu ảnh, kiểm tra độ tương đồng trên màn hình hiện tại.
    Giúp xác nhận rằng ảnh mới đã đủ rõ ràng.
    """
    if not os.path.exists(template_path):
        return None

    template = cv2.imread(template_path)
    if template is None:
        return None

    res = cv2.matchTemplate(screenshot_bgr, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return max_val


# ==================== MAIN ====================
def main():
    print("=" * 65)
    print("   GBF BOT - CÔNG CỤ SCAN LẠI ẢNH TEMPLATE (scan_templates.py)")
    print("=" * 65)
    print()
    print("Hướng dẫn:")
    print("  1. Đảm bảo thiết bị Android / giả lập đang kết nối ADB")
    print("  2. Điều hướng game đến màn hình có element cần scan")
    print("  3. Chọn số tương ứng với nút cần scan từ menu bên dưới")
    print("  4. Script sẽ chụp màn hình và cho bạn kéo chọn vùng bằng chuột")
    print("  5. Nhấn ENTER để lưu, R để chọn lại, S để bỏ qua")
    print()

    # Kiểm tra kết nối ADB
    print("[ADB] Kiểm tra kết nối thiết bị...")
    if not auto_detect_device():
        devices_output = run_adb(['devices'])
        if not devices_output:
            print("[ERROR] Không thể kết nối với ADB. Vui lòng kiểm tra:")
            print("  - ADB đã được cài đặt và có trong PATH chưa?")
            print("  - Thiết bị / giả lập đã được kết nối chưa?")
            return
        print(f"[ADB] Thiết bị:\n{devices_output}\n")
    else:
        print(f"[ADB] Đang sử dụng thiết bị: {DEVICE_ADDRESS}\n")

    while True:
        print("\n" + "=" * 50)
        print("  DANH SÁCH CÁC NÚT CẦN SCAN:")
        for idx, tmpl in enumerate(TEMPLATES_TO_SCAN):
            status = "[Đã có file]" if os.path.exists(tmpl['path']) else "[Chưa có file]"
            print(f"  [{idx + 1}] {tmpl['name']} - {tmpl['path']} {status}")
        print("  [A] Quét tất cả các nút theo thứ tự")
        print("  [Q] Thoát chương trình")
        print("=" * 50)
        
        choice = input("\nNhập lựa chọn của bạn (1-4, A, Q): ").strip().lower()
        if choice == 'q':
            print("[EXIT] Đã thoát chương trình.")
            break
            
        selected_templates = []
        if choice == 'a':
            selected_templates = TEMPLATES_TO_SCAN
        else:
            try:
                val = int(choice)
                if 1 <= val <= len(TEMPLATES_TO_SCAN):
                    selected_templates = [TEMPLATES_TO_SCAN[val - 1]]
                else:
                    print("[ERROR] Lựa chọn không hợp lệ!")
                    continue
            except ValueError:
                print("[ERROR] Lựa chọn không hợp lệ!")
                continue

        # Tiến hành scan các template đã chọn
        for tmpl in selected_templates:
            print(f"\n{'='*65}")
            print(f"  BẮT ĐẦU SCAN: {tmpl['name']}")
            print(f"  File đích: {tmpl['path']}")
            print(f"  Gợi ý: {tmpl['hint']}")
            print(f"{'='*65}")

            input(f"\n  -> Điều hướng game đến màn hình có [{tmpl['name']}], rồi nhấn ENTER để chụp màn hình...")

            # Vòng lặp cho phép chụp lại nếu cần
            while True:
                try:
                    screenshot = take_screenshot()
                except RuntimeError as e:
                    print(f"[ERROR] {e}")
                    retry = input("Thử lại? (y/n): ").strip().lower()
                    if retry != 'y':
                        break
                    continue

                # Hiển thị cửa sổ chọn ROI
                try:
                    roi = select_roi_interactive(screenshot, tmpl)
                except SystemExit:
                    print("[EXIT] Đã thoát scan tool.")
                    return

                if roi is None:
                    break

                x1, y1, x2, y2 = roi
                if x2 - x1 < 5 or y2 - y1 < 5:
                    print("[WARN] Vùng chọn quá nhỏ. Hãy kéo rộng hơn.")
                    continue

                # Crop ảnh
                cropped = screenshot[y1:y2, x1:x2]

                # Preview và xác nhận
                confirm = preview_and_confirm(cropped, tmpl)

                if confirm is True:
                    # Lưu ảnh
                    save_template(cropped, tmpl['path'])

                    # Kiểm tra confidence ngay sau khi lưu
                    conf = verify_confidence(screenshot, tmpl['path'])
                    if conf is not None:
                        status = "✓ TỐT" if conf >= 0.75 else "⚠ THẤP"
                        print(f"  [VERIFY] Confidence trên màn hình hiện tại: {conf:.3f} - {status}")
                        if conf < 0.75:
                            print("  [WARN] Confidence thấp! Có thể ảnh bị mờ, thiếu chi tiết, hoặc chọn sai vùng.")
                            retry = input("  Chọn lại vùng? (y/n): ").strip().lower()
                            if retry == 'y':
                                continue
                    break

                elif confirm is False:
                    # Chọn lại
                    print("[INFO] Chọn lại vùng ROI...")
                    continue
                else:
                    # Bỏ qua (None)
                    break

    print("\n[INFO] Đã hoàn thành tác vụ scan.")


if __name__ == "__main__":
    main()
