import subprocess
import time
import os
import cv2
import numpy as np
from PIL import Image
import urllib.request
import json
import adbutils

# ==================== KẾT NỐI ADB & ĐIỀU KHIỂN (adbutils) ====================
DEVICE_ADDRESS = None  # Sẽ được gán tự động qua auto_detect_device()
_adb_device = None     # adbutils.AdbDevice — dùng cho screenshot/tap/swipe nhanh


def get_adb_path():
    """Tự động tìm kiếm đường dẫn adb.exe trên Windows giống cách UMAT hoạt động."""
    import shutil
    # 1. Thử kiểm tra xem hệ thống có nhận diện lệnh "adb" trực tiếp hay không
    system_adb = shutil.which("adb")
    if system_adb:
        return "adb"
        
    # 2. Thử tìm kiếm trong thư viện adbutils của Python nếu người dùng có cài
    try:
        import site
        from pathlib import Path
        for site_pkg in site.getsitepackages():
            path = Path(site_pkg) / 'adbutils' / 'binaries' / 'adb.exe'
            if path.exists():
                return str(path)
    except Exception:
        pass
        
    # 3. Thử tìm kiếm trong các thư mục cài đặt giả lập thông dụng trên Windows
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
            
    # Mặc định trả về "adb" và hy vọng người dùng sẽ thêm vào PATH
    return "adb"

def auto_detect_device():
    """
    Tự động quét và chọn thiết bị ADB đang online thông qua adbutils (socket trực tiếp).
    Nhanh hơn so với subprocess vì không cần spawn process mới mỗi lần gọi.
    """
    global DEVICE_ADDRESS, _adb_device
    try:
        devices = adbutils.adb.device_list()
    except Exception as e:
        print(f"[ADB ERROR] Không thể quét thiết bị qua adbutils: {e}")
        return False

    if not devices:
        print("[ADB ERROR] Không tìm thấy thiết bị ADB nào đang kết nối!")
        print("[ADB INFO] Hãy chắc chắn:")
        print("           - Thiết bị đã bật USB Debugging / Wireless Debugging")
        print("           - Giả lập (emulator) đang chạy")
        return False

    if len(devices) == 1:
        _adb_device = devices[0]
        DEVICE_ADDRESS = _adb_device.serial
        print(f"[ADB] Tự động chọn thiết bị duy nhất: {DEVICE_ADDRESS}")
    else:
        print(f"[ADB] Phát hiện {len(devices)} thiết bị đang kết nối:")
        for i, dev in enumerate(devices):
            print(f"      [{i}] {dev.serial}")
        _adb_device = devices[0]
        DEVICE_ADDRESS = _adb_device.serial
        print(f"[ADB] Tự động chọn thiết bị đầu tiên: {DEVICE_ADDRESS}")
        print("[ADB INFO] Để chọn thiết bị khác, sửa biến DEVICE_ADDRESS thủ công.")

    return True


def connect_device(address):
    """
    Kết nối tới thiết bị ADB theo địa chỉ cụ thể (dùng bởi GUI).
    Tạo adbutils device object để dùng cho các thao tác nhanh.
    """
    global DEVICE_ADDRESS, _adb_device
    try:
        # Thử connect nếu là wireless device (có dấu ":")
        if ":" in address:
            try:
                adbutils.adb.connect(address, timeout=3.0)
            except Exception:
                pass  # Có thể đã kết nối sẵn
        _adb_device = adbutils.adb.device(serial=address)
        DEVICE_ADDRESS = address
        print(f"[ADB] Đã kết nối thiết bị qua adbutils: {DEVICE_ADDRESS}")
        return True
    except Exception as e:
        print(f"[ADB ERROR] Không thể kết nối tới {address} qua adbutils: {e}")
        # Fallback: chỉ set DEVICE_ADDRESS cho run_adb subprocess
        DEVICE_ADDRESS = address
        _adb_device = None
        print(f"[ADB WARNING] Fallback: dùng subprocess cho thiết bị {address}")
        return True


def run_adb(command):
    """Thực thi một lệnh ADB qua subprocess (giữ lại cho backward compatibility với GUI)."""
    adb_path = get_adb_path()
    full_cmd = [adb_path]
    if DEVICE_ADDRESS:
        full_cmd.extend(['-s', DEVICE_ADDRESS])
    full_cmd.extend(command)
    
    try:
        # Nếu là lấy ảnh chụp màn hình, ta cần nhận bytes thô
        if 'screencap' in command:
            result = subprocess.run(full_cmd, capture_output=True, check=True, shell=True)
            return result.stdout
        else:
            result = subprocess.run(full_cmd, capture_output=True, text=True, check=True, shell=True)
            return result.stdout.strip()
    except Exception as e:
        print(f"[ADB ERROR] Lỗi thực thi {full_cmd}: {e}")
        return None

def take_screenshot():
    """
    Chụp màn hình qua adbutils (socket trực tiếp) — nhanh hơn ~2x so với subprocess.
    Trả về đối tượng PIL Image.
    """
    global _adb_device
    if _adb_device is None:
        raise Exception("Chưa kết nối thiết bị ADB! Gọi auto_detect_device() hoặc connect_device() trước.")
    try:
        return _adb_device.screenshot()
    except Exception as e:
        print(f"[ERROR] Chụp màn hình lỗi: {e}")
        raise Exception(f"Không thể chụp màn hình từ thiết bị: {e}")

def tap(x, y):
    """Chạm vào tọa độ (x, y) trên màn hình — dùng adbutils (nhanh hơn subprocess)."""
    global _adb_device
    print(f"[INPUT] Tap tại tọa độ: ({x}, {y})")
    if _adb_device:
        _adb_device.click(int(x), int(y))
    else:
        run_adb(['shell', 'input', 'tap', str(int(x)), str(int(y))])

def swipe(x1, y1, x2, y2, duration_ms=500):
    """Vuốt màn hình từ (x1, y1) đến (x2, y2) — dùng adbutils."""
    global _adb_device
    if _adb_device:
        _adb_device.swipe(int(x1), int(y1), int(x2), int(y2), duration_ms / 1000.0)
    else:
        run_adb(['shell', 'input', 'swipe', str(x1), str(y1), str(x2), str(y2), str(duration_ms)])

def reload_page():
    """Tải lại trang trình duyệt trong game."""
    print("[ACTION] Đang tải lại trang (Reload)...")
    
    # Cách 1: Thử tìm ảnh nút reload trên màn hình và click (cách chính xác nhất)
    try:
        screen = take_screenshot()
        reload_btn = find_template(screen, "assets/buttons/reload.webp", confidence=0.85)
        if reload_btn:
            print("[ACTION] Nhấp nút reload bằng ảnh mẫu...")
            tap(reload_btn[0], reload_btn[1])
            time.sleep(1.5)  # Giảm từ 3.0s → 1.5s, loop bên ngoài tự check kết quả
            return
    except Exception as e:
        print(f"[WARNING] Tìm nút reload bằng hình ảnh lỗi: {e}")
        
    # Cách 2: Vuốt xuống để kích hoạt tự động tải lại trang (Pull-to-refresh)
    try:
        w, h = take_screenshot().size
        print("[ACTION] Thực hiện vuốt xuống để kéo trang tải lại (Pull-to-refresh)...")
        swipe(w // 2, int(h * 0.35), w // 2, int(h * 0.75), 400)
        time.sleep(1.5)  # Giảm từ 3.0s → 1.5s
        return
    except Exception as e:
        print(f"[WARNING] Cử chỉ vuốt tải lại lỗi: {e}")
        
    # Cách 3: Gửi phím F5 qua ADB keyevent
    print("[ACTION] Gửi keyevent F5 qua ADB...")
    if _adb_device:
        _adb_device.shell("input keyevent 135")
    else:
        run_adb(['shell', 'input', 'keyevent', '135'])
    time.sleep(1.5)  # Giảm từ 3.0s → 1.5s

# ==================== TEMPLATE MATCHING (THAY THẾ OCR — NHANH HƠN ~50-100x) ====================
# Cache ảnh template trong RAM để tránh đọc disk mỗi lần gọi find_template
_template_cache = {}

def find_template(screen_pil, template_path, confidence=0.8, region=None, grayscale=False):
    """
    Tìm kiếm template hình ảnh trên màn hình bằng OpenCV (hỗ trợ giới hạn vùng quét).
    
    Args:
        screen_pil: PIL Image chụp màn hình.
        template_path: Đường dẫn tới file ảnh template.
        confidence: Ngưỡng confidence tối thiểu (0.0 - 1.0).
        region: Tuple (left, top, right, bottom) giới hạn vùng quét — giảm thời gian matching.
        grayscale: Nếu True, chuyển sang ảnh xám trước khi matching (nhanh hơn ~30%).
    """
    global _template_cache
    screen_pil_original = screen_pil
    if region:
        # region: (left, top, right, bottom)
        screen_pil = screen_pil.crop(region)
    
    screen_np = np.array(screen_pil)
    
    # Chuyển đổi màu theo chế độ
    if grayscale:
        screen_cv = cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
        cache_key = f"{template_path}__gray"
    else:
        screen_cv = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
        cache_key = template_path
    
    # Dùng cache để tránh đọc file từ disk mỗi lần (tiết kiệm ~10-50ms/call)
    if cache_key not in _template_cache:
        if grayscale:
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        else:
            template = cv2.imread(template_path)
        if template is None:
            print(f"[ERROR] Không tìm thấy file template tại: {template_path}")
            return None
        _template_cache[cache_key] = template
    template = _template_cache[cache_key]
        
    h, w = template.shape[:2]
    sh, sw = screen_cv.shape[:2]
    
    # Kiểm tra kích thước để tránh lỗi OpenCV assertion
    if sw < w or sh < h:
        print(f"[WARNING] Vùng quét ({sw}x{sh}) nhỏ hơn template ({w}x{h}). Tự động quét toàn màn hình...")
        return find_template(screen_pil_original, template_path, confidence, region=None, grayscale=grayscale)

    res = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    
    print(f"[DEBUG] Khớp ảnh '{template_path}': {max_val:.3f} (>= {confidence})")
    
    if max_val >= confidence:
        # Trả về tâm của ảnh template
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        if region:
            center_x += region[0]
            center_y += region[1]
        return center_x, center_y
    return None

# ==================== LUỒNG ĐIỀU KHIỂN CHÍNH (GBF BASIC LOOP) ====================
class GBFController:
    def __init__(self, mode="full_auto", discord_webhook_url=""):
        self.mode = mode  # "auto" (spam attack) hoặc "full_auto" (click full auto + reload)
        self.discord_webhook_url = discord_webhook_url
        self.is_running = True
        self.rocket_coords    = None  # Cache tọa độ nút rocket    — scan 1 lần dùng mãi
        self.full_auto_coords = None  # Cache tọa độ nút Full Auto — scan 1 lần dùng mãi
        self.reload_coords    = None  # Cache tọa độ nút Reload    — scan 1 lần dùng mãi
        self.ok_coords        = None  # Cache tọa độ nút OK        — scan 1 lần dùng mãi
        self.attack_coords    = None  # Cache tọa độ nút Attack    — scan 1 lần dùng mãi
        self.attack_region    = None  # Cache vùng quét của nút Attack (cực nhanh)

    def send_discord_webhook(self, message):
        """Gửi thông báo tới Discord Webhook."""
        if not self.discord_webhook_url:
            return
        
        data = {"content": message}
        req = urllib.request.Request(
            self.discord_webhook_url, 
            data=json.dumps(data).encode('utf-8'), 
            headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            print("[DISCORD] Đã gửi thông báo thành công!")
        except Exception as e:
            print(f"[DISCORD ERROR] Lỗi khi gửi webhook: {e}")

    def check_captcha(self, screen):
        """
        Kiểm tra màn hình xem có Captcha 'Access Verification' không.
        Dùng Template Matching thay OCR — nhanh hơn ~50-100x (~20ms thay vì ~1500ms).
        """
        w, h = screen.size
        # Captcha popup thường xuất hiện ở vùng giữa-trên màn hình
        captcha_region = (0, int(h * 0.15), w, int(h * 0.55))
        
        result = find_template(screen, "assets/headers/captcha_header.webp",
                               confidence=0.75, region=captcha_region, grayscale=True)
        if result:
            return True
        return False

    def detect_start_screen(self):
        """
        Kiểm tra đang ở màn hình Chọn Party.
        Dùng Template Matching thay OCR.
        """
        print("[PROCESS] Đang nhận diện màn hình khởi đầu...")
        screen = take_screenshot()
        
        # Kiểm tra màn hình chọn Party bằng các template party set 1-4
        for i in range(1, 5):
            party_tpl = f"assets/buttons/party_set_{i}.webp"
            if os.path.exists(party_tpl):
                party = find_template(screen, party_tpl, confidence=0.80, grayscale=True)
                if party:
                    print(f"[DETECT] Nhận diện: Màn hình Chọn Party (khớp {os.path.basename(party_tpl)})")
                    return "party"
                
        return "unknown"
    def cache_rocket_coords(self):
        """
        Scan nút rocket 1 lần khi khởi động và lưu tọa độ.
        Nếu đã có cache thì bỏ qua.
        """
        if self.rocket_coords:
            return  # Đã cache rồi, không cần scan lại
        print("[INIT] Đang scan và cache tọa độ nút rocket (1 lần duy nhất)...")
        screen = take_screenshot()
        w, h = screen.size
        bottom_right_region = (int(w * 0.5), int(h * 0.5), w, h)
        coords = find_template(screen, "assets/buttons/rocket.webp", confidence=0.85, region=bottom_right_region)
        if coords:
            self.rocket_coords = coords
            print(f"[INIT] Đã cache tọa độ rocket: {self.rocket_coords}")
        else:
            print("[INIT] Chưa thấy nút rocket ở màn hình này, sẽ cache khi gặp lần đầu.")

    def wait_for_combat_start(self):
        """Đợi cho đến khi vào trận đấu (Quét liên tục cho đến khi phát hiện nút Attack)."""
        print("[PROCESS] Đang đợi tải vào trận đấu...")
        attempt = 0
        start_time = time.time()  # Đo thời gian thực thay vì estimate
        while self.is_running:
            screen = take_screenshot()
            w, h = screen.size

            # Quét Captcha mỗi 15 lần lặp (~1.5 giây một lần)
            # Bỏ qua lần đầu (attempt=0) vì game chưa load, captcha chưa thể xuất hiện
            if attempt > 0 and attempt % 15 == 0:
                if self.check_captcha(screen):
                    print("[ALERT] PHÁT HIỆN CAPTCHA 'Access Verification'!")
                    self.send_discord_webhook("@everyone Phát hiện Captcha 'Access Verification'! Bot đã tự động dừng.")
                    self.is_running = False
                    return None, None

            # Sử dụng vùng quét giới hạn để tăng tốc nhận diện nút Attack
            if self.attack_region:
                search_region = self.attack_region
            else:
                search_region = (int(w * 0.45), int(h * 0.3), w, int(h * 0.85))

            attack_btn = find_template(screen, "assets/buttons/attack.webp", confidence=0.85, region=search_region)
            if attack_btn:
                elapsed = time.time() - start_time
                print(f"[SUCCESS] Đã phát hiện nút Attack sau {elapsed:.1f} giây!")
                
                # Lưu cache tọa độ và vùng quét nhỏ xung quanh
                self.attack_coords = attack_btn
                self.attack_region = (
                    max(0, attack_btn[0] - 200),
                    max(0, attack_btn[1] - 150),
                    min(w, attack_btn[0] + 200),
                    min(h, attack_btn[1] + 150)
                )
                print(f"[CACHE] Đã lưu tọa độ Attack: {self.attack_coords}, Vùng quét: {self.attack_region}")
                
                # Trả về cả screen để play_combat dùng lại, tránh chụp thêm
                return attack_btn, screen

            attempt += 1
            if attempt % 50 == 0:
                elapsed = time.time() - start_time
                print(f"[INFO] Vẫn đang đợi tải vào trận đấu (đã quét {attempt} lần, {elapsed:.1f}s thực tế)...")
            time.sleep(0.02)

        return None, None

    def play_combat(self, attack_coords, combat_screen=None):
        """Bước 3: Thực hiện đánh theo chế độ tự chọn.
        
        Args:
            attack_coords: Tọa độ nút Attack đã phát hiện.
            combat_screen: Ảnh chụp màn hình đã có sẵn từ wait_for_combat_start,
                           dùng lại để tránh chụp thêm (tiết kiệm ~1-2 giây delay).
        """
        if not self.is_running:
            return

        print("[PROCESS] Bắt đầu vòng lặp combat...")
        screen = combat_screen if combat_screen is not None else take_screenshot()
        w, h = screen.size
        
        combat_turn = 0
        max_turns = 50  # Giới hạn an toàn tránh lặp vô hạn

        while self.is_running and combat_turn < max_turns:
            combat_turn += 1
            print(f"[COMBAT] Bắt đầu lượt xử lý combat thứ {combat_turn}...")

            # --- Bước A: Thực hiện hành động tấn công tương ứng với chế độ ---
            if self.mode == "auto":
                # Chế độ Auto Spam Attack
                print("[MODE] Đang chạy chế độ AUTO (Nhấn Attack → reload)...")

                # Lần đầu tiên sử dụng attack_coords truyền vào, các lượt sau tự scan tìm nút Attack (sử dụng cache region)
                current_attack_coords = attack_coords if combat_turn == 1 else find_template(screen, "assets/buttons/attack.webp", confidence=0.85, region=self.attack_region)

                if current_attack_coords:
                    # Cache reload nếu chưa có
                    if not self.reload_coords:
                        print("[CACHE] Quét vị trí Reload để cache...")
                        rl = find_template(screen, "assets/buttons/reload.webp", confidence=0.85)
                        if rl:
                            self.reload_coords = rl
                            print(f"[CACHE] Đã cache Reload coords: {self.reload_coords}")

                    # Nhấn nút Attack 1 lần
                    tap(current_attack_coords[0], current_attack_coords[1])
                    time.sleep(0.5)
                else:
                    print("[WARNING] Không tìm thấy nút Attack trong lượt này.")

                # Reload bằng tọa độ cache hoặc fallback
                if self.reload_coords:
                    print(f"[ACTION] Tap reload tại cache {self.reload_coords}...")
                    tap(self.reload_coords[0], self.reload_coords[1])
                else:
                    reload_page()
                time.sleep(1.5)

            elif self.mode == "full_auto":
                # Chế độ Full Auto + Reload
                print("[MODE] Đang chạy chế độ FULL AUTO + RELOAD...")

                # Đảm bảo có cache Full Auto và Reload
                if not self.full_auto_coords or not self.reload_coords:
                    print("[CACHE] Scan vị trí Full Auto và Reload để cache...")
                    if not self.full_auto_coords:
                        fa = find_template(screen, "assets/buttons/full_auto.webp", confidence=0.85)
                        if fa:
                            self.full_auto_coords = fa
                            print(f"[CACHE] Đã cache Full Auto coords: {self.full_auto_coords}")
                    if not self.reload_coords:
                        rl = find_template(screen, "assets/buttons/reload.webp", confidence=0.85)
                        if rl:
                            self.reload_coords = rl
                            print(f"[CACHE] Đã cache Reload coords: {self.reload_coords}")

                # Kích hoạt Full Auto
                if self.full_auto_coords:
                    tap(self.full_auto_coords[0], self.full_auto_coords[1])
                else:
                    tap(int(w * 0.15), int(h * 0.45))
                print("[ACTION] Đã kích hoạt Full Auto. Đang chờ nút Attack biến mất...")

                # Chờ attack biến mất -> reload ngay
                attack_gone = False
                for _ in range(150):  # Timeout tối đa 15 giây (150 lần x 0.1s)
                    if not self.is_running:
                        return
                    screen = take_screenshot()
                    attack_still_here = find_template(screen, "assets/buttons/attack.webp", confidence=0.85, region=self.attack_region)
                    if not attack_still_here:
                        print("[ACTION] Nút Attack đã biến mất! Reload ngay lập tức...")
                        attack_gone = True
                        if not self.reload_coords:
                            rl = find_template(screen, "assets/buttons/reload.webp", confidence=0.85)
                            if rl:
                                self.reload_coords = rl
                                print(f"[CACHE] Cache Reload coords: {self.reload_coords}")
                        break
                    time.sleep(0.02)

                if not attack_gone:
                    print("[WARNING] Timeout chờ attack biến mất. Tiến hành reload anyway...")

                # Reload bằng tọa độ cache hoặc fallback
                if self.reload_coords:
                    print(f"[ACTION] Tap reload tại cache {self.reload_coords}...")
                    tap(self.reload_coords[0], self.reload_coords[1])
                else:
                    reload_page()
                time.sleep(1.5)

            elif self.mode == "full_auto_quick":
                # Chế độ Full Auto + Instant Reload (không chờ attack biến mất)
                print("[MODE] Đang chạy chế độ FULL AUTO + INSTANT RELOAD...")

                # Đảm bảo có cache Full Auto và Reload
                if not self.full_auto_coords or not self.reload_coords:
                    print("[CACHE] Scan vị trí Full Auto và Reload để cache...")
                    if not self.full_auto_coords:
                        fa = find_template(screen, "assets/buttons/full_auto.webp", confidence=0.85)
                        if fa:
                            self.full_auto_coords = fa
                            print(f"[CACHE] Đã cache Full Auto coords: {self.full_auto_coords}")
                    if not self.reload_coords:
                        rl = find_template(screen, "assets/buttons/reload.webp", confidence=0.85)
                        if rl:
                            self.reload_coords = rl
                            print(f"[CACHE] Đã cache Reload coords: {self.reload_coords}")

                # Kích hoạt Full Auto
                if self.full_auto_coords:
                    tap(self.full_auto_coords[0], self.full_auto_coords[1])
                else:
                    tap(int(w * 0.15), int(h * 0.45))
                time.sleep(0.5)

                # Reload bằng tọa độ cache hoặc fallback
                if self.reload_coords:
                    print(f"[ACTION] Tap reload tại cache {self.reload_coords}...")
                    tap(self.reload_coords[0], self.reload_coords[1])
                else:
                    reload_page()
                time.sleep(1.5)

            # --- Bước B: Chờ sau khi reload và nhận diện trạng thái tiếp theo ---
            print("[PROCESS] Đang chờ và nhận diện trạng thái sau reload...")
            state_detected = None
            
            # Lặp kiểm tra trong khoảng tối đa 15 giây (150 lần quét x 0.1 giây)
            for scan_i in range(150):
                if not self.is_running:
                    return

                screen = take_screenshot()

                # Quét Captcha mỗi 15 lần quét (~1.5 giây một lần)
                if scan_i > 0 and scan_i % 15 == 0:
                    if self.check_captcha(screen):
                        print("[ALERT] PHÁT HIỆN CAPTCHA 'Access Verification'!")
                        self.send_discord_webhook("@everyone Phát hiện Captcha 'Access Verification'! Bot đã tự động dừng.")
                        self.is_running = False
                        return

                # 1. Kiểm tra màn hình kết quả (EXP, Loot) — dùng lại screen đã chụp, tránh chụp thêm
                if self.check_is_battle_ended(screen):
                    print("[SUCCESS] Trận đấu kết thúc hoàn toàn (phát hiện màn hình EXP/Loot).")
                    state_detected = "ended"
                    break

                # 2. Kiểm tra xem nút Attack có quay lại không (quay lại combat do boss chưa chết)
                current_attack = find_template(screen, "assets/buttons/attack.webp", confidence=0.85, region=self.attack_region)
                if current_attack:
                    print("[INFO] Boss chưa chết! Phát hiện lại nút Attack. Tiếp tục lượt combat tiếp theo...")
                    state_detected = "combat"
                    break

                time.sleep(0.02)

            if state_detected == "ended":
                break
            elif state_detected == "combat":
                # Tiếp tục vòng lặp
                continue
            else:
                # Quá 15s không nhận diện được trạng thái kết thúc hay combat. 
                # Có thể do game bị đơ hoặc tải trang quá chậm.
                print("[WARNING] Không phát hiện màn hình EXP hay nút Attack sau 15s. Thử reload lại trang...")
                if self.reload_coords:
                    tap(self.reload_coords[0], self.reload_coords[1])
                else:
                    reload_page()
                time.sleep(1.5)
                screen = take_screenshot()

        if combat_turn >= max_turns:
            print(f"[WARNING] Đạt giới hạn tối đa {max_turns} lượt combat. Kết thúc combat.")

    def check_is_battle_ended(self, screen=None):
        """
        Kiểm tra màn hình kết quả bằng Template Matching (thay OCR).
        Tìm các header: EXP Gained, Loot Collected, Battle Concluded.
        Nhanh hơn ~50x so với OCR (~20ms thay vì ~800ms).

        Args:
            screen: PIL Image đã có sẵn để dùng lại, tránh chụp thêm nếu caller đã có.
                    Nếu None sẽ tự chụp màn hình mới.
        """
        if screen is None:
            screen = take_screenshot()
        w, h = screen.size
        # Vùng kết quả thường hiển thị ở phần trên-giữa màn hình
        result_region = (0, int(h * 0.1), w, int(h * 0.5))

        # Kiểm tra các template header kết quả trận đấu
        end_templates = [
            "assets/headers/exp_gained_header.webp",
            "assets/headers/loot_collected_header.webp",
            "assets/headers/battle_concluded_header.webp",
        ]
        for tpl in end_templates:
            result = find_template(screen, tpl, confidence=0.80,
                                  region=result_region, grayscale=True)
            if result:
                tpl_name = os.path.basename(tpl)
                print(f"[DETECT] Trận đấu kết thúc! Nhận diện header: {tpl_name}")
                return True
        return False

    def wait_for_battle_finished(self):
        """Lặp kiểm tra cho đến khi trận đấu kết thúc hoàn toàn."""
        print("[PROCESS] Đang đợi trận đấu kết thúc...")
        while True:
            if not self.is_running:
                break
            if self.check_is_battle_ended():
                break
            time.sleep(0.1)  # 0.1s/lần scan

    def return_to_party_selection(self):
        """Bước 4: Nhấn nút quay lại màn hình chọn Summon sau khi kết thúc trận."""
        if not self.is_running:
            return

        # Nếu đã có tọa độ rocket cache → tap thẳng, không cần scan
        if self.rocket_coords:
            print(f"[ACTION] Dùng tọa độ rocket đã cache {self.rocket_coords}, tap ngay...")
            tap(self.rocket_coords[0], self.rocket_coords[1])
        else:
            # Lần đầu tiên: scan để tìm và cache tọa độ rocket
            print("[ACTION] Chưa có cache rocket, đang scan lần đầu...")
            screen = take_screenshot()
            w, h = screen.size
            bottom_right_region = (int(w * 0.5), int(h * 0.5), w, h)
            found_rocket = False

            for _ in range(120):  # Đợi tối đa ~12 giây (120 lần x 0.1s)
                if not self.is_running:
                    return
                screen = take_screenshot()
                back_btn = find_template(screen, "assets/buttons/rocket.webp", confidence=0.85, region=bottom_right_region)
                if back_btn:
                    self.rocket_coords = back_btn
                    print(f"[ACTION] Đã cache tọa độ rocket: {self.rocket_coords}. Tap ngay!")
                    tap(back_btn[0], back_btn[1])
                    found_rocket = True
                    break
                time.sleep(0.1)

            if not self.is_running:
                return

            if not found_rocket:
                print("[WARNING] Không tìm thấy nút rocket. Thử reload trang bằng ADB...")
                reload_page()
                time.sleep(1.5)
                if not self.is_running:
                    return
                screen = take_screenshot()
                back_btn = find_template(screen, "assets/buttons/rocket.webp", confidence=0.85, region=bottom_right_region)
                if back_btn:
                    self.rocket_coords = back_btn
                    print(f"[ACTION] Đã cache tọa độ rocket (sau reload): {self.rocket_coords}")
                    tap(back_btn[0], back_btn[1])
                else:
                    w, h = screen.size
                    print("[WARNING] Vẫn không tìm thấy nút rocket. Nhấp tọa độ mặc định Play Again.")
                    tap(w // 2, int(h * 0.85))

        if not self.is_running:
            return

        # Thay sleep cứng bằng poll loop: chờ nút OK xuất hiện = màn Party đã load xong
        print("[PROCESS] Đang chờ màn hình Party load (quét nút OK)...")
        for _ in range(200):  # Timeout tối đa ~20 giây (200 lần x 0.1s)
            if not self.is_running:
                return
            screen = take_screenshot()
            w, h = screen.size
            if self.ok_coords:
                # Quét trong vùng nhỏ xung quanh ok_coords để kiểm tra nhanh xem nút OK đã xuất hiện chưa
                # Vùng quét phải lớn hơn kích thước template ok.webp (433x109)
                ok_region = (
                    max(0, self.ok_coords[0] - 250),
                    max(0, self.ok_coords[1] - 80),
                    min(w, self.ok_coords[0] + 250),
                    min(h, self.ok_coords[1] + 80)
                )
                ok = find_template(screen, "assets/buttons/ok.webp", confidence=0.85, region=ok_region)
            else:
                ok = find_template(screen, "assets/buttons/ok.webp", confidence=0.85)

            if ok:
                if not self.ok_coords:
                    self.ok_coords = ok  # Chỉ cache tọa độ OK ở lần đầu tiên phát hiện
                    print(f"[SUCCESS] Màn Party đã load! Đã cache tọa độ OK: {self.ok_coords}")
                else:
                    print(f"[SUCCESS] Màn Party đã load (Xác nhận qua cache OK coords)!")
                return
            time.sleep(0.1)

        print("[WARNING] Timeout chờ màn Party. start_loop sẽ tự xử lý ở vòng tiếp.")

    def start_loop(self, loop_count=1):
        """Chạy vòng lặp cơ bản. loop_count = -1 chạy vô hạn, hoặc X lần."""
        current_loop = 0
        while True:
            if not self.is_running:
                print("[BOT] Đang dừng hoạt động...")
                break
                
            if loop_count != -1 and current_loop >= loop_count:
                print(f"[SUCCESS] Đã hoàn thành đủ {loop_count} vòng lặp!")
                break
                
            loop_str = f"vòng {current_loop + 1}" if loop_count != -1 else f"vòng {current_loop + 1} (Vô hạn)"
            print(f"\n===== BẮT ĐẦU BOT GBF - {loop_str.upper()} (CHẾ ĐỘ: {self.mode.upper()}) =====")
            
            # Bước 1: Kiểm tra màn hình (chỉ vòng đầu — vòng 2+ bỏ qua vì biết chắc đang ở màn Party)
            if current_loop == 0:
                screen_type = self.detect_start_screen()
            else:
                screen_type = "party"  # Sau khi tap rocket, game luôn quay về màn Party
                print("[FAST] Vòng tiếp theo — bỏ qua detect, xác định là màn Party ngay.")
            
            if screen_type == "unknown":
                print("[ERROR] Bạn không ở màn hình Chọn Party! Dừng bot.")
                break
                
            if screen_type == "party":
                if current_loop == 0:
                    print("[SUCCESS] Xác nhận đã ở màn Chọn Party. Tiến hành click OK...")
                
                # Nếu đã có tọa độ OK cache, tap thẳng lập tức không cần chụp màn hình/matching lại
                if self.ok_coords:
                    print(f"[CACHE] Tap OK tại tọa độ cache {self.ok_coords}...")
                    tap(self.ok_coords[0], self.ok_coords[1])
                else:
                    screen = take_screenshot()
                    w, h = screen.size
                    ok = find_template(screen, "assets/buttons/ok.webp", confidence=0.85)
                    if ok:
                        self.ok_coords = ok
                        print(f"[CACHE] Đã cache OK coords: {self.ok_coords}")
                        print(f"[CACHE] Tap OK tại tọa độ cache {self.ok_coords}...")
                        tap(self.ok_coords[0], self.ok_coords[1])
                    else:
                        print("[WARNING] Không thấy nút OK, nhấp tọa độ mặc định.")
                        tap(w // 2, int(h * 0.83))
                # Không cần sleep cứng — wait_for_combat_start sẽ poll đến khi thấy Attack
            
            if not self.is_running:
                break
                
            time.sleep(4.0)

            # Đợi vào trận và lấy tọa độ nút Attack + screen hiện tại
            attack_coords, combat_screen = self.wait_for_combat_start()
            
            if not self.is_running:
                break
                
            # Bước 3: Đánh / Full Auto / Tải lại trang (truyền screen để dùng lại)
            self.play_combat(attack_coords, combat_screen)
            
            if not self.is_running:
                break
                
            # Bước 4: Nhấn nút quay trở lại màn chọn Summon
            self.return_to_party_selection()
            
            print(f"===== HOÀN THÀNH VÒNG LẶP THỨ {current_loop + 1} =====\n")
            current_loop += 1
            # Không sleep — rocket đã chuyển màn, vòng tiếp tap OK ngay lập tức

# ==================== ĐIỂM CHẠY THỬ ====================
if __name__ == "__main__":
    # Đọc cấu hình webhook đã lưu
    config_file = "config.txt"
    saved_webhook = ""
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                saved_webhook = f.read().strip()
        except Exception:
            pass

    # Nhập webhook url
    prompt_text = "Nhập Discord Webhook URL"
    if saved_webhook:
        prompt_text += f" (Nhấn Enter để dùng webhook đã lưu: {saved_webhook[:30]}...)"
    else:
        prompt_text += " (để trống nếu không dùng)"
    
    user_input = input(prompt_text + ": ").strip()
    
    if user_input:
        webhook_url = user_input
        # Lưu lại vào file config
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                f.write(webhook_url)
            print("[INFO] Đã lưu Webhook URL mới vào config.txt")
        except Exception as e:
            print(f"[ERROR] Không thể lưu config.txt: {e}")
    else:
        webhook_url = saved_webhook

    # Tự động scan và kết nối thiết bị ADB đang hoạt động
    if not auto_detect_device():
        print("[BOT] Không tìm được thiết bị. Vui lòng kiểm tra kết nối ADB rồi chạy lại.")
        exit(1)

    # Khởi chạy thử nghiệm bot với chế độ Full Auto + Reload
    # Mặc định chạy 1 vòng lặp để thử nghiệm, bạn có thể truyền số vòng lặp khác, vd: loop_count=5 hoặc loop_count=-1 (vô hạn)
    bot = GBFController(mode="full_auto", discord_webhook_url=webhook_url)
    bot.start_loop(loop_count=1)
