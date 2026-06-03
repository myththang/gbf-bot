import subprocess
import time
import os
import cv2
import numpy as np
import pytesseract
from PIL import Image
import urllib.request
import json

# ==================== CẤU HÌNH TESSERACT ====================
# Thiết lập đường dẫn tới Tesseract executable (tương tự UMAT)
if os.name == 'nt':
    possible_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(
            os.getenv('USERNAME', '')
        )
    ]
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break

# ==================== KẾT NỐI ADB & ĐIỀU KHIỂN ====================
DEVICE_ADDRESS = None  # Sẽ được gán tự động qua auto_detect_device()


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
    Tự động quét và chọn thiết bị ADB đang online.
    - Nếu chỉ có 1 thiết bị → chọn luôn.
    - Nếu có nhiều thiết bị → in danh sách và chọn cái đầu tiên.
    - Nếu không có thiết bị nào → báo lỗi và thoát.
    """
    global DEVICE_ADDRESS
    adb_path = get_adb_path()
    try:
        result = subprocess.run(
            [adb_path, 'devices'],
            capture_output=True, text=True, shell=True, timeout=10
        )
        output = result.stdout.strip()
    except Exception as e:
        print(f"[ADB ERROR] Không thể chạy 'adb devices': {e}")
        return False

    lines = output.splitlines()
    # Dòng đầu là header "List of devices attached", bỏ qua
    device_lines = [
        line for line in lines[1:]
        if line.strip() and 'offline' not in line and 'unauthorized' not in line
    ]

    online_devices = []
    for line in device_lines:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == 'device':
            online_devices.append(parts[0])

    if not online_devices:
        print("[ADB ERROR] Không tìm thấy thiết bị ADB nào đang kết nối!")
        print("[ADB INFO] Hãy chắc chắn:")
        print("           - Thiết bị đã bật USB Debugging / Wireless Debugging")
        print("           - Giả lập (emulator) đang chạy")
        print(f"[ADB RAW OUTPUT]\n{output}")
        return False

    if len(online_devices) == 1:
        DEVICE_ADDRESS = online_devices[0]
        print(f"[ADB] Tự động chọn thiết bị duy nhất: {DEVICE_ADDRESS}")
    else:
        print(f"[ADB] Phát hiện {len(online_devices)} thiết bị đang kết nối:")
        for i, dev in enumerate(online_devices):
            print(f"      [{i}] {dev}")
        # Mặc định chọn thiết bị đầu tiên
        DEVICE_ADDRESS = online_devices[0]
        print(f"[ADB] Tự động chọn thiết bị đầu tiên: {DEVICE_ADDRESS}")
        print("[ADB INFO] Để chọn thiết bị khác, sửa biến DEVICE_ADDRESS thủ công.")

    return True

def run_adb(command):
    """Thực thi một lệnh ADB."""
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
    """Chụp màn hình qua ADB và trả về đối tượng PIL Image (tương tự UMAT)."""
    raw_data = run_adb(['shell', 'screencap', '-p'])
    if not raw_data:
        raise Exception("Không thể chụp màn hình từ thiết bị qua ADB")
    
    # Sửa lỗi ký tự xuống dòng trên Windows (\r\n -> \n)
    if os.name == 'nt':
        raw_data = raw_data.replace(b'\r\n', b'\n')
        
    # Tạo PIL Image từ dữ liệu bytes
    try:
        # Có thể dùng OpenCV hoặc PIL trực tiếp
        # Chuyển bytes thô thành numpy array để OpenCV xử lý nếu cần
        nparr = np.frombuffer(raw_data, np.uint8)
        img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # Chuyển BGR (OpenCV) thành RGB (PIL)
        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_rgb)
    except Exception as e:
        print(f"[ERROR] Giải mã ảnh chụp màn hình lỗi: {e}")
        # Phương pháp thay thế dùng PIL trực tiếp
        import io
        return Image.open(io.BytesIO(raw_data))

def tap(x, y):
    """Chạm vào tọa độ (x, y) trên màn hình."""
    print(f"[INPUT] Tap tại tọa độ: ({x}, {y})")
    run_adb(['shell', 'input', 'tap', str(int(x)), str(int(y))])

def swipe(x1, y1, x2, y2, duration_ms=500):
    """Vuốt màn hình từ (x1, y1) đến (x2, y2)."""
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
        
    # Cách 3: Gửi phím F5 qua ADB keyevent 135
    print("[ACTION] Gửi keyevent F5 qua ADB...")
    run_adb(['shell', 'input', 'keyevent', '135'])
    time.sleep(1.5)  # Giảm từ 3.0s → 1.5s

# ==================== XỬ LÝ ẢNH & TESSERACT OCR ====================
def preprocess_for_ocr(pil_img, threshold_val=180):
    """
    Tiền xử lý ảnh giống UMAT để tăng độ chính xác của OCR.
    Chuyển về ảnh xám và nhị phân hóa (thresholding) để nổi bật chữ trắng/đen.
    """
    img_np = np.array(pil_img)
    # Chuyển sang ảnh xám
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    # Nhị phân hóa
    _, thresh = cv2.threshold(gray, threshold_val, 255, cv2.THRESH_BINARY)
    return thresh

def get_text_from_region(pil_img, region=None, threshold_val=180, scale_factor=1):
    """
    Trích xuất chữ từ vùng chỉ định trên ảnh chụp màn hình sử dụng Tesseract.
    
    Args:
        pil_img: PIL Image
        region: Tuple (left, top, right, bottom). Nếu None, sẽ OCR toàn bộ ảnh.
        threshold_val: Giá trị ngưỡng nhị phân hóa.
        scale_factor: Hệ số phóng to ảnh (mặc định = 1, không phóng to).
    """
    if region:
        cropped = pil_img.crop(region)
    else:
        cropped = pil_img
        
    if scale_factor > 1:
        w, h = cropped.size
        try:
            resample_filter = Image.Resampling.LANCZOS
        except AttributeError:
            resample_filter = Image.LANCZOS
        cropped = cropped.resize((int(w * scale_factor), int(h * scale_factor)), resample_filter)
        
    # Áp dụng tiền xử lý
    processed_np = preprocess_for_ocr(cropped, threshold_val)
    
    # Chuyển lại sang PIL để đưa vào Tesseract
    processed_pil = Image.fromarray(processed_np)
    
    # Cấu hình tesseract chạy nhanh (PSM 6: Giả định một khối văn bản đồng nhất)
    custom_config = r'--oem 3 --psm 6'
    try:
        text = pytesseract.image_to_string(processed_pil, config=custom_config, lang='eng')
        return text.strip()
    except Exception as e:
        print(f"[OCR ERROR] Không thể nhận diện văn bản: {e}")
        return ""

# Cache ảnh template trong RAM để tránh đọc disk mỗi lần gọi find_template
_template_cache = {}

def find_template(screen_pil, template_path, confidence=0.8, region=None):
    """ Tìm kiếm template hình ảnh trên màn hình bằng OpenCV (hỗ trợ giới hạn vùng quét)."""
    global _template_cache
    if region:
        # region: (left, top, right, bottom)
        screen_pil = screen_pil.crop(region)
        
    screen_np = cv2.cvtColor(np.array(screen_pil), cv2.COLOR_RGB2BGR)

    # Dùng cache để tránh đọc file từ disk mỗi lần (tiết kiệm ~10-50ms/call)
    if template_path not in _template_cache:
        template = cv2.imread(template_path)
        if template is None:
            print(f"[ERROR] Không tìm thấy file template tại: {template_path}")
            return None
        _template_cache[template_path] = template
    template = _template_cache[template_path]
        
    h, w = template.shape[:2]
    res = cv2.matchTemplate(screen_np, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    
    print(f"[DEBUG] Khớp ảnh '{template_path}': độ tương đồng tối đa = {max_val:.3f} (yêu cầu >= {confidence})")
    
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

    def is_captcha_text(self, text):
        """Kiểm tra xem chuỗi text có chứa các dấu hiệu của Captcha không (sử dụng Fuzzy Matching & Levenshtein)."""
        if not text:
            return False
            
        import re
        import unicodedata
        
        # Chuẩn hóa Unicode (phát hiện và chuyển đổi các ký tự đặc biệt/ligature như ﬁ -> fi)
        text_lower = text.lower()
        text_normalized = unicodedata.normalize('NFKD', text_lower)
        
        # 1. Khớp chính xác cụm từ hoặc kiểm tra các từ khóa bảo mật khác
        if "access verification" in text_normalized:
            return True
            
        # 2. Kiểm tra sự xuất hiện đồng thời của các biến thể Access và Verification
        access_patterns = ["access", "acess", "acces", "accs", "aqcess"]
        verification_patterns = ["verification", "verif", "verify", "ver1fication", "venification", "verfication"]
        
        has_access = any(p in text_normalized for p in access_patterns)
        has_verification = any(p in text_normalized for p in verification_patterns)
        if has_access and has_verification:
            return True
            
        # 3. Sử dụng thuật toán Levenshtein Distance kiểm tra từng từ đơn lẻ
        words = re.findall(r'[a-z0-9]+', text_normalized)
        
        def levenshtein_distance(s1, s2):
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            if len(s2) == 0:
                return len(s1)
            previous_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            return previous_row[-1]

        found_access_fuzzy = False
        found_verification_fuzzy = False
        
        for w in words:
            if len(w) >= 4:
                # Từ gần giống "access" (khoảng cách <= 2)
                if levenshtein_distance(w, "access") <= 2:
                    found_access_fuzzy = True
                # Từ gần giống "verification" (khoảng cách <= 3)
                if levenshtein_distance(w, "verification") <= 3:
                    found_verification_fuzzy = True
                # Từ gần giống "verify" (khoảng cách <= 1)
                if levenshtein_distance(w, "verify") <= 1:
                    found_verification_fuzzy = True
                    
        if found_access_fuzzy and found_verification_fuzzy:
            return True
            
        return False

    def check_captcha(self, screen):
        """Kiểm tra màn hình xem có Captcha 'Access Verification' không."""
        w, h = screen.size
        # Quét khu vực giữa màn hình nơi popup Captcha thường xuất hiện
        region = (0, int(h * 0.2), w, int(h * 0.8))

        # scale_factor=1: captcha text đủ lớn để OCR không cần phóng to
        # → tiết kiệm ~800-1500ms so với scale_factor=2
        text = get_text_from_region(screen, region, threshold_val=150, scale_factor=1)
        if self.is_captcha_text(text):
            return True

        # Fallback threshold khác (không phóng to để tránh lag)
        text_fallback = get_text_from_region(screen, region, threshold_val=200, scale_factor=1)
        if self.is_captcha_text(text_fallback):
            return True

        return False

    def detect_start_screen(self):
        """Kiểm tra xem đang ở màn hình Chọn Summon hay màn hình Chọn Party."""
        print("[PROCESS] Đang nhận diện màn hình khởi đầu...")
        screen = take_screenshot()
        w, h = screen.size
        title_region = (0, int(h * 0.05), w, int(h * 0.18))
        
        extracted_text = get_text_from_region(screen, title_region, threshold_val=150)
        print(f"[OCR RESULT] Nhận diện màn hình: '{extracted_text}'")
        
        # Kiểm tra màn hình chọn Summon
        summon_keywords = ["Summon", "Select", "Support", "Chon"]
        for kw in summon_keywords:
            if kw.lower() in extracted_text.lower():
                return "summon"
                
        # Kiểm tra màn hình chọn Party
        party_keywords = ["Party", "Set A", "Set B", "Ex A", "Ex B", "Choose"]
        for kw in party_keywords:
            if kw.lower() in extracted_text.lower():
                return "party"
                
        return "unknown"

    def select_summon_and_start(self):
        """Bước 2: Tìm và click chọn summon đầu tiên -> Nhấp nút OK trên hộp thoại xác nhận."""
        screen = take_screenshot()
        w, h = screen.size
        
        # Giả lập việc chọn summon hỗ trợ đầu tiên: Thường nằm khoảng 25% chiều cao màn hình.
        # Nhấp vào summon đầu tiên
        print("[ACTION] Chọn Summon hỗ trợ đầu tiên...")
        tap(w // 2, int(h * 0.25))
        time.sleep(2.0)
        
        # Vuốt màn hình lên (cuộn trang xuống) để đưa nút OK bị khuất lên hiển thị
        print("[ACTION] Vuốt màn hình lên để đưa nút OK lên vùng hiển thị...")
        swipe(w // 2, int(h * 0.8), w // 2, int(h * 0.4), 300)
        time.sleep(1.5)
        
        # Kiểm tra hộp thoại xác nhận bắt đầu trận đấu, tìm nút "OK" bằng Template Matching hoặc OCR
        print("[ACTION] Tìm nút OK để bắt đầu phó bản...")
        screen = take_screenshot()
        
        # Cách 1: Sử dụng Template Matching để tìm nút OK
        ok_coords = find_template(screen, "assets/buttons/ok.webp", confidence=0.85)
        if ok_coords:
            tap(ok_coords[0], ok_coords[1])
        else:
            # Cách 2: Tọa độ nút OK mặc định (ví dụ ở giữa dưới hộp thoại, khoảng 60% chiều cao)
            print("[WARNING] Không tìm thấy nút OK bằng ảnh mẫu, nhấp tọa độ mặc định.")
            tap(w // 2, int(h * 0.60))
            
        time.sleep(1.0) # Đợi tải vào trận đấu (chuyển sang wait_for_combat_start để xử lý Captcha)

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

            # Quét Captcha mỗi 10 lần lặp (thay vì 3) để giảm lag OCR
            # Bỏ qua lần đầu (attempt=0) vì game chưa load, captcha chưa thể xuất hiện
            if attempt > 0 and attempt % 10 == 0:
                if self.check_captcha(screen):
                    print("[ALERT] PHÁT HIỆN CAPTCHA 'Access Verification'!")
                    self.send_discord_webhook("@everyone Phát hiện Captcha 'Access Verification'! Bot đã tự động dừng.")
                    self.is_running = False
                    return None, None

            attack_btn = find_template(screen, "assets/buttons/attack.webp", confidence=0.85)
            if attack_btn:
                elapsed = time.time() - start_time
                print(f"[SUCCESS] Đã phát hiện nút Attack sau {elapsed:.1f} giây!")
                # Trả về cả screen để play_combat dùng lại, tránh chụp thêm
                return attack_btn, screen

            attempt += 1
            if attempt % 10 == 0:
                elapsed = time.time() - start_time
                print(f"[INFO] Vẫn đang đợi tải vào trận đấu (đã quét {attempt} lần, {elapsed:.1f}s thực tế)...")
            time.sleep(0.5)

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

                # Lần đầu tiên sử dụng attack_coords truyền vào, các lượt sau tự scan tìm nút Attack
                current_attack_coords = attack_coords if combat_turn == 1 else find_template(screen, "assets/buttons/attack.webp", confidence=0.85)

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
                for _ in range(60):  # Timeout tối đa 30 giây
                    if not self.is_running:
                        return
                    screen = take_screenshot()
                    attack_still_here = find_template(screen, "assets/buttons/attack.webp", confidence=0.85)
                    if not attack_still_here:
                        print("[ACTION] Nút Attack đã biến mất! Reload ngay lập tức...")
                        attack_gone = True
                        if not self.reload_coords:
                            rl = find_template(screen, "assets/buttons/reload.webp", confidence=0.85)
                            if rl:
                                self.reload_coords = rl
                                print(f"[CACHE] Cache Reload coords: {self.reload_coords}")
                        break
                    time.sleep(0.5)

                if not attack_gone:
                    print("[WARNING] Timeout chờ attack biến mất. Tiến hành reload anyway...")

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
            
            # Lặp kiểm tra trong khoảng tối đa 15 giây (30 lần quét x 0.5 giây)
            for scan_i in range(30):
                if not self.is_running:
                    return

                screen = take_screenshot()

                # Quét Captcha mỗi 10 lần quét (giảm tần suất để tránh lag OCR)
                if scan_i > 0 and scan_i % 10 == 0:
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
                current_attack = find_template(screen, "assets/buttons/attack.webp", confidence=0.85)
                if current_attack:
                    print("[INFO] Boss chưa chết! Phát hiện lại nút Attack. Tiếp tục lượt combat tiếp theo...")
                    state_detected = "combat"
                    break

                time.sleep(0.5)

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
        """Kiểm tra màn hình kết quả thông qua OCR (tìm chữ EXP, Loot...).

        Args:
            screen: PIL Image đã có sẵn để dùng lại, tránh chụp thêm nếu caller đã có.
                    Nếu None sẽ tự chụp màn hình mới.
        """
        if screen is None:
            screen = take_screenshot()
        w, h = screen.size
        # Vùng đọc chữ kết quả (ví dụ: EXP Gained, Loot, Results ở giữa màn hình)
        result_region = (0, int(h * 0.2), w, int(h * 0.5))
        text = get_text_from_region(screen, result_region, threshold_val=180)

        keywords = ["EXP", "Loot", "Gained", "Result", "Concluded", "Tap"]
        for keyword in keywords:
            if keyword.lower() in text.lower():
                print(f"[OCR DETECTED] Trận đấu kết thúc! Nhận diện được chữ: '{keyword}'")
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
            time.sleep(0.5)  # 0.5s/lần scan

    def return_to_summon_selection(self):
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

            for _ in range(24):  # Đợi tối đa ~12 giây (24 lần x 0.5s)
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
                time.sleep(0.5)

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
        for _ in range(40):  # Timeout tối đa ~20 giây (40 lần x 0.5s)
            if not self.is_running:
                return
            screen = take_screenshot()
            ok = find_template(screen, "assets/buttons/ok.webp", confidence=0.85)
            if ok:
                self.ok_coords = ok  # Cache luôn để start_loop dùng ngay
                print(f"[SUCCESS] Màn Party đã load! Cache OK coords: {self.ok_coords}")
                return
            time.sleep(0.5)

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
                print("[FAST] Vòng tiếp theo — bỏ qua detect/OCR, xác định là màn Party ngay.")
            
            if screen_type == "unknown":
                print("[ERROR] Bạn không ở màn hình Chọn Summon hoặc Chọn Party! Dừng bot.")
                break
                
            if screen_type == "summon":
                print("[SUCCESS] Xác nhận đang ở màn hình Chọn Summon. Tiến hành chọn Summon...")
                # Bước 2: Chọn Summon và nhấn OK bắt đầu phó bản
                self.select_summon_and_start()
            elif screen_type == "party":
                if current_loop == 0:
                    print("[SUCCESS] Xác nhận đã ở màn Chọn Party. Tiến hành click OK...")
                screen = take_screenshot()
                w, h = screen.size
                # Dùng cache nếu có, chỉ scan lần đầu
                if not self.ok_coords:
                    ok = find_template(screen, "assets/buttons/ok.webp", confidence=0.85)
                    if ok:
                        self.ok_coords = ok
                        print(f"[CACHE] Đã cache OK coords: {self.ok_coords}")
                if self.ok_coords:
                    print(f"[CACHE] Tap OK tại {self.ok_coords}...")
                    tap(self.ok_coords[0], self.ok_coords[1])
                else:
                    print("[WARNING] Không thấy nút OK, nhấp tọa độ mặc định.")
                    tap(w // 2, int(h * 0.83))
                # Không cần sleep cứng — wait_for_combat_start sẽ poll đến khi thấy Attack
            
            if not self.is_running:
                break
                
            # Đợi vào trận và lấy tọa độ nút Attack + screen hiện tại
            attack_coords, combat_screen = self.wait_for_combat_start()
            
            if not self.is_running:
                break
                
            # Bước 3: Đánh / Full Auto / Tải lại trang (truyền screen để dùng lại)
            self.play_combat(attack_coords, combat_screen)
            
            if not self.is_running:
                break
                
            # Bước 4: Nhấn nút quay trở lại màn chọn Summon
            self.return_to_summon_selection()
            
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
