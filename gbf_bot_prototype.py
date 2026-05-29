import subprocess
import time
import os
import cv2
import numpy as np
import pytesseract
from PIL import Image

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

def get_text_from_region(pil_img, region=None, threshold_val=180):
    """
    Trích xuất chữ từ vùng chỉ định trên ảnh chụp màn hình sử dụng Tesseract.
    
    Args:
        pil_img: PIL Image
        region: Tuple (left, top, right, bottom). Nếu None, sẽ OCR toàn bộ ảnh.
    """
    if region:
        cropped = pil_img.crop(region)
    else:
        cropped = pil_img
        
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

def find_template(screen_pil, template_path, confidence=0.8, region=None):
    """ Tìm kiếm template hình ảnh trên màn hình bằng OpenCV (hỗ trợ giới hạn vùng quét)."""
    if region:
        # region: (left, top, right, bottom)
        screen_pil = screen_pil.crop(region)
        
    screen_np = cv2.cvtColor(np.array(screen_pil), cv2.COLOR_RGB2BGR)
    template = cv2.imread(template_path)
    if template is None:
        print(f"[ERROR] Không tìm thấy file template tại: {template_path}")
        return None
        
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
    def __init__(self, mode="full_auto"):
        self.mode = mode  # "auto" (spam attack) hoặc "full_auto" (click full auto + reload)
        self.is_running = True
        self.rocket_coords    = None  # Cache tọa độ nút rocket    — scan 1 lần dùng mãi
        self.full_auto_coords = None  # Cache tọa độ nút Full Auto — scan 1 lần dùng mãi
        self.reload_coords    = None  # Cache tọa độ nút Reload    — scan 1 lần dùng mãi
        self.ok_coords        = None  # Cache tọa độ nút OK        — scan 1 lần dùng mãi
        
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
            
        time.sleep(5.0) # Đợi tải vào trận đấu

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
        POLL_INTERVAL = 0.5
        while self.is_running:
            screen = take_screenshot()
            attack_btn = find_template(screen, "assets/buttons/attack.webp", confidence=0.85)
            if attack_btn:
                print(f"[SUCCESS] Đã phát hiện nút Attack sau {attempt * POLL_INTERVAL:.1f} giây!")
                # Trả về cả screen để play_combat dùng lại, tránh chụp thêm
                return attack_btn, screen
            
            attempt += 1
            if attempt % 10 == 0:
                print(f"[INFO] Vẫn đang đợi tải vào trận đấu (đã quét {attempt} lần, ~{attempt * POLL_INTERVAL:.1f}s)...")
            time.sleep(POLL_INTERVAL)
            
        return None, None

    def play_combat(self, attack_coords, combat_screen=None):
        """Bước 3: Thực hiện đánh theo chế độ tự chọn.
        
        Args:
            attack_coords: Tọa độ nút Attack đã phát hiện.
            combat_screen: Ảnh chụp màn hình đã có sẵn từ wait_for_combat_start,
                           dùng lại để tránh chụp thêm (tiết kiệm ~1-2 giây delay).
        """
        if not self.is_running or not attack_coords:
            return
        # Dùng lại screen đã có, hoặc chụp mới nếu không có
        screen = combat_screen if combat_screen is not None else take_screenshot()
        w, h = screen.size

        if self.mode == "auto":
            # CHẾ ĐỘ AUTO (Nhấn Attack 1 lần, chờ biến mất rồi reload — giống Full Auto)
            print("[MODE] Đang chạy chế độ AUTO (Nhấn Attack → chờ biến mất → reload)...")

            # --- Bước A: Cache tọa độ reload nếu chưa có ---
            if not self.reload_coords:
                print("[CACHE] Lần đầu chạy AUTO — scan vị trí Reload để cache...")
                rl = find_template(screen, "assets/buttons/reload.webp", confidence=0.85)
                if rl:
                    self.reload_coords = rl
                    print(f"[CACHE] Đã cache Reload coords: {self.reload_coords}")
                else:
                    print("[CACHE] Chưa thấy nút Reload ở screen này, sẽ scan lại sau.")
            else:
                print(f"[CACHE] Dùng cache — Reload: {self.reload_coords}")

            # --- Bước B: Nhấn nút Attack 1 lần ---
            tap(attack_coords[0], attack_coords[1])
            print("[ACTION] Đã nhấn Attack. Đang chờ nút Attack biến mất để reload...")

            # --- Bước C: Chờ attack biến mất → reload ngay, không chờ cứng ---
            attack_gone = False
            for _ in range(60):  # Timeout tối đa 30 giây
                if not self.is_running:
                    return
                screen_check = take_screenshot()
                attack_still_here = find_template(screen_check, "assets/buttons/attack.webp", confidence=0.85)
                if not attack_still_here:
                    print("[ACTION] Nút Attack đã biến mất! Reload ngay lập tức...")
                    attack_gone = True
                    # Nếu chưa có cache reload, scan từ screen này luôn
                    if not self.reload_coords:
                        rl = find_template(screen_check, "assets/buttons/reload.webp", confidence=0.85)
                        if rl:
                            self.reload_coords = rl
                            print(f"[CACHE] Cache Reload coords (sau attack mất): {self.reload_coords}")
                    break
                time.sleep(0.5)

            if not attack_gone:
                print("[WARNING] Timeout chờ attack biến mất. Tiến hành reload anyway...")

            # --- Bước D: Reload bằng tọa độ cache, không cần scan ---
            if self.reload_coords:
                print(f"[ACTION] Tap reload tại cache {self.reload_coords} (không scan)...")
                tap(self.reload_coords[0], self.reload_coords[1])
                time.sleep(1.5)
            else:
                reload_page()  # Fallback nếu chưa cache được

            # --- Bước E: Chờ màn hình EXP xuất hiện ---
            print("[PROCESS] Đang chờ màn hình EXP/kết quả xuất hiện...")
            found_result = False
            for i in range(30):  # Tối đa ~15 giây
                if not self.is_running:
                    break
                if self.check_is_battle_ended():
                    found_result = True
                    break
                time.sleep(0.5)

            if found_result:
                print("[SUCCESS] Đã xác nhận trận đấu kết thúc.")
            else:
                if self.is_running:
                    print("[WARNING] Không phát hiện được trận kết thúc. Tiếp tục đợi...")
                    self.wait_for_battle_finished()

        elif self.mode == "full_auto":
            # CHẾ ĐỘ FULL AUTO + RELOAD
            print("[MODE] Đang chạy chế độ FULL AUTO + RELOAD...")
            # screen đã có sẵn từ tham số, không cần chụp lại

            # --- Bước A: Scan full_auto + reload CHỈ lần đầu, từ lần 2 dùng cache ---
            if not self.full_auto_coords or not self.reload_coords:
                print("[CACHE] Lần đầu chạy — scan vị trí Full Auto và Reload để cache...")
                if not self.full_auto_coords:
                    fa = find_template(screen, "assets/buttons/full_auto.webp", confidence=0.85)
                    if fa:
                        self.full_auto_coords = fa
                        print(f"[CACHE] Đã cache Full Auto coords: {self.full_auto_coords}")
                    else:
                        print("[CACHE] Không tìm thấy Full Auto bằng ảnh, dùng tọa độ mặc định.")
                if not self.reload_coords:
                    rl = find_template(screen, "assets/buttons/reload.webp", confidence=0.85)
                    if rl:
                        self.reload_coords = rl
                        print(f"[CACHE] Đã cache Reload coords: {self.reload_coords}")
                    else:
                        print("[CACHE] Chưa thấy nút Reload ở screen này, sẽ scan lại sau.")
            else:
                print(f"[CACHE] Dùng cache — Full Auto: {self.full_auto_coords}, Reload: {self.reload_coords}")

            # --- Bước B: Click Full Auto bằng tọa độ cache (hoặc mặc định) ---
            if self.full_auto_coords:
                tap(self.full_auto_coords[0], self.full_auto_coords[1])
            else:
                tap(int(w * 0.15), int(h * 0.45))
            print("[ACTION] Đã kích hoạt Full Auto. Đang chờ nút Attack biến mất để reload...")

            # --- Bước C: Chờ attack biến mất → reload ngay, không chờ cứng ---
            attack_gone = False
            for _ in range(60):  # Timeout tối đa 30 giây
                if not self.is_running:
                    return
                screen = take_screenshot()
                attack_still_here = find_template(screen, "assets/buttons/attack.webp", confidence=0.85)
                if not attack_still_here:
                    print("[ACTION] Nút Attack đã biến mất! Reload ngay lập tức...")
                    attack_gone = True
                    # Nếu chưa có cache reload, scan từ screen này luôn
                    if not self.reload_coords:
                        rl = find_template(screen, "assets/buttons/reload.webp", confidence=0.85)
                        if rl:
                            self.reload_coords = rl
                            print(f"[CACHE] Cache Reload coords (sau attack mất): {self.reload_coords}")
                    break
                time.sleep(0.5)

            if not attack_gone:
                print("[WARNING] Timeout chờ attack biến mất. Tiến hành reload anyway...")

            # --- Bước D: Reload bằng tọa độ cache, không cần scan ---
            if self.reload_coords:
                print(f"[ACTION] Tap reload tại cache {self.reload_coords} (không scan)...")
                tap(self.reload_coords[0], self.reload_coords[1])
                time.sleep(1.5)
            else:
                reload_page()  # Fallback nếu chưa cache được

            # --- Bước E: Chờ màn hình EXP xuất hiện ---
            print("[PROCESS] Đang chờ màn hình EXP/kết quả xuất hiện...")
            found_result = False
            for i in range(30):  # Tối đa ~15 giây
                if not self.is_running:
                    break
                if self.check_is_battle_ended():
                    found_result = True
                    break
                time.sleep(0.5)

            if found_result:
                print("[SUCCESS] Đã xác nhận trận đấu kết thúc.")
            else:
                if self.is_running:
                    print("[WARNING] Không phát hiện được trận kết thúc. Tiếp tục đợi...")
                    self.wait_for_battle_finished()

    def check_is_battle_ended(self):
        """Kiểm tra màn hình kết quả thông qua OCR (tìm chữ EXP, Loot...)."""
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
    # Tự động scan và kết nối thiết bị ADB đang hoạt động
    if not auto_detect_device():
        print("[BOT] Không tìm được thiết bị. Vui lòng kiểm tra kết nối ADB rồi chạy lại.")
        exit(1)

    # Khởi chạy thử nghiệm bot với chế độ Full Auto + Reload
    # Mặc định chạy 1 vòng lặp để thử nghiệm, bạn có thể truyền số vòng lặp khác, vd: loop_count=5 hoặc loop_count=-1 (vô hạn)
    bot = GBFController(mode="full_auto")
    bot.start_loop(loop_count=1)
