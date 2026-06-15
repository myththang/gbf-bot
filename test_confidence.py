# -*- coding: utf-8 -*-
"""
Kiểm tra confidence của tất cả ảnh template đang được bot sử dụng
trên màn hình hiện tại của thiết bị.

Phiên bản tối ưu: Bao gồm cả Button + Header templates (thay thế OCR).
"""
import os
import sys
import cv2
import numpy as np
import adbutils

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ==================== TEMPLATE LISTS ====================
BUTTON_TEMPLATES = [
    "assets/buttons/attack.webp",
    "assets/buttons/full_auto.webp",
    "assets/buttons/ok.webp",
    "assets/buttons/reload.webp",
    "assets/buttons/rocket.webp",
    "assets/buttons/party_set_1.webp",
    "assets/buttons/party_set_2.webp",
    "assets/buttons/party_set_3.webp",
    "assets/buttons/party_set_4.webp",
]

HEADER_TEMPLATES = [
    "assets/headers/captcha_header.webp",
    "assets/headers/exp_gained_header.webp",
    "assets/headers/loot_collected_header.webp",
    "assets/headers/battle_concluded_header.webp",
]

ALL_TEMPLATES = BUTTON_TEMPLATES + HEADER_TEMPLATES
TARGET_CONFIDENCE = 0.85


def take_screenshot():
    """Chụp màn hình qua adbutils, trả về BGR numpy array."""
    devices = adbutils.adb.device_list()
    if not devices:
        raise RuntimeError("Không tìm thấy thiết bị ADB nào!")
    device = devices[0]
    print(f"[ADB] Thiết bị: {device.serial}")
    pil_img = device.screenshot()
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def check_template(screen, path, target_conf):
    """Kiểm tra confidence của 1 template. Trả về (max_val, status, max_loc, size)."""
    if not os.path.exists(path):
        return None, "MISSING", None, None

    tmpl = cv2.imread(path)
    if tmpl is None:
        return None, "READ_ERR", None, None

    th, tw = tmpl.shape[:2]
    res = cv2.matchTemplate(screen, tmpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val >= target_conf:
        status = "PASS ✓"
    elif max_val >= 0.70:
        status = "OK ~"
    else:
        status = "FAIL ✗"

    return max_val, status, max_loc, (tw, th)


# ==================== MAIN ====================
print("=" * 70)
print("  KIỂM TRA CONFIDENCE - TẤT CẢ TEMPLATE ĐANG SỬ DỤNG")
print("  (Buttons + Headers thay thế OCR)")
print("=" * 70)

print("\n[ADB] Đang chụp màn hình thiết bị...")
screen = take_screenshot()
print(f"[OK]  Màn hình: {screen.shape[1]}x{screen.shape[0]} px\n")

pass_count = fail_count = missing_count = 0


def print_section(title, templates):
    global pass_count, fail_count, missing_count
    print(f"\n  {'─' * 60}")
    print(f"  {title}")
    print(f"  {'─' * 60}")

    for path in templates:
        max_val, status, max_loc, size = check_template(screen, path, TARGET_CONFIDENCE)
        name = os.path.basename(path)

        if status == "MISSING":
            print(f"  [???] {name:<40s} ← KHÔNG TÌM THẤY FILE!")
            missing_count += 1
            continue
        if status == "READ_ERR":
            print(f"  [ERR] {name:<40s} ← KHÔNG ĐỌC ĐƯỢC FILE!")
            missing_count += 1
            continue

        bar_len = int(max_val * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)

        if "PASS" in status:
            pass_count += 1
        else:
            fail_count += 1

        print(f"  [{status}]  {name}")
        print(f"           [{bar}] {max_val:.4f}  (vị trí: {max_loc}, size: {size[0]}x{size[1]})")


print_section("NÚT BẤM (Buttons)", BUTTON_TEMPLATES)
print_section("HEADER NHẬN DIỆN TRẠNG THÁI (thay OCR)", HEADER_TEMPLATES)

total = len(ALL_TEMPLATES)
print(f"\n{'=' * 70}")
print(f"  KẾT QUẢ:  PASS {pass_count}/{total}  |  FAIL/OK {fail_count}  |  MISSING {missing_count}")
print(f"  Ngưỡng:   confidence >= {TARGET_CONFIDENCE}")
if fail_count > 0:
    print("  [GỢI Ý]   Các ảnh FAIL/OK cần scan lại bằng: python scan_templates.py")
elif missing_count > 0:
    print("  [GỢI Ý]   Các ảnh MISSING cần được tạo bằng: python scan_templates.py")
else:
    print("  [TUYỆT VỜI] Tất cả ảnh đều đạt ngưỡng 0.85!")
print("=" * 70)
