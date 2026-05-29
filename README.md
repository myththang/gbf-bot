# GBF ADB Bot (Python)

Bot tự động chơi **Granblue Fantasy** trên thiết bị Android thật hoặc giả lập thông qua **ADB (Android Debug Bridge)**, sử dụng **OpenCV** để nhận diện ảnh và **Tesseract OCR** để đọc text trên màn hình.

> ⚠️ **Disclaimer:** Sử dụng bot trong game có thể vi phạm điều khoản dịch vụ của KMR. Tác giả không chịu trách nhiệm về bất kỳ hậu quả nào từ việc sử dụng tool này.

---

## 📁 Cấu trúc thư mục

```
gbf-adb-bot/
├── gbf_bot_prototype.py       # Bot chính: điều khiển vòng lặp chiến đấu tự động
├── gbf_gui.py                 # Giao diện GUI (tkinter) để điều khiển bot
├── scan_templates.py          # Tool chụp và cắt ảnh template từ thiết bị
├── test_confidence.py         # Tool kiểm tra độ tương đồng của ảnh template
├── control_scripts_summary.md # Tài liệu tổng hợp các script điều khiển
├── requirements.txt           # Các thư viện Python cần thiết
└── assets/
    ├── buttons/               # Ảnh template các nút bấm trong game
    ├── headers/               # Ảnh template các tiêu đề màn hình
    ├── summons/               # Ảnh template các summon
    └── items/                 # Ảnh template các item
```

---

## ⚙️ Yêu cầu hệ thống

- **Python 3.8+**
- **ADB (Android Debug Bridge)** đã được cài đặt và có trong PATH, hoặc sử dụng ADB từ giả lập (LDPlayer, MuMu, v.v.)
- **Tesseract OCR** (chỉ cần cho OCR text):
  - Windows: [Tải tại đây](https://github.com/UB-Mannheim/tesseract/wiki)
  - Cài vào `C:\Program Files\Tesseract-OCR\`

---

## 🚀 Cài đặt

### 1. Clone repo

```bash
git clone https://github.com/YOUR_USERNAME/gbf-adb-bot.git
cd gbf-adb-bot
```

### 2. Tạo virtual environment (khuyến nghị)

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# hoặc
source venv/bin/activate  # Linux/Mac
```

### 3. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

---

## 🎮 Cách sử dụng

### Chạy Bot chính

```bash
python gbf_bot_prototype.py
```

Bot sẽ tự động:
1. Quét và kết nối thiết bị ADB đang online
2. Nhận diện màn hình hiện tại (Chọn Summon / Chọn Party)
3. Chạy vòng lặp chiến đấu tự động (Full Auto hoặc Auto)

### Chạy với GUI

```bash
python gbf_gui.py
```

### Scan lại ảnh template (khi cần cập nhật)

```bash
python scan_templates.py
```

### Kiểm tra độ tương đồng template

```bash
python test_confidence.py
```

---

## ⚙️ Cấu hình

Mở `gbf_bot_prototype.py` và chỉnh tham số tại phần cuối file:

```python
bot = GBFController(mode="full_auto")  # hoặc "auto"
bot.start_loop(loop_count=5)           # -1 = vô hạn
```

| Tham số | Mô tả |
|---------|-------|
| `mode="full_auto"` | Kích hoạt Full Auto → đợi attack biến mất → reload |
| `mode="auto"` | Nhấn Attack 1 lần → đợi attack biến mất → reload |
| `loop_count=-1` | Chạy vô hạn |
| `loop_count=N` | Chạy N vòng rồi dừng |

---

## 🔧 Xử lý sự cố

**ADB không tìm thấy thiết bị:**
- Đảm bảo thiết bị bật USB Debugging hoặc Wireless Debugging
- Nếu dùng giả lập, kiểm tra port ADB (LDPlayer: 5554, MuMu: 16384, v.v.)
- Thử chạy: `adb devices` trong terminal

**Ảnh template không khớp (confidence thấp):**
- Chạy `scan_templates.py` để chụp lại ảnh template từ thiết bị của bạn
- Ảnh template phụ thuộc vào độ phân giải màn hình thiết bị

**Tesseract không tìm thấy:**
- Cài Tesseract theo link ở trên
- Hoặc thêm đường dẫn thủ công trong `gbf_bot_prototype.py`

---

## 📝 License

MIT License - Xem file [LICENSE](LICENSE) để biết thêm chi tiết.
