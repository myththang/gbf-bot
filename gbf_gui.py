import sys
import os
import json
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit,
    QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon

# Import logic bot nguyên mẫu
from gbf_bot_prototype import GBFController, DEVICE_ADDRESS, get_adb_path, connect_device

# Palette màu tối giao diện hiện đại (lấy cảm hứng từ UMAT và MAA)
COLORS = {
    'bg_darkest': '#1a1a1a',
    'bg_dark': '#242424',
    'bg_card': '#2d2d2d',
    'bg_input': '#383838',
    'bg_hover': '#404040',
    'border': '#3a3a3a',
    'border_light': '#4a4a4a',
    'text_primary': '#ffffff',
    'text_secondary': '#b0b0b0',
    'text_muted': '#707070',
    'accent_primary': '#7c5cff',  # Tím hiện đại
    'accent_green': '#4caf50',
    'accent_red': '#ef5350',
}

MAIN_STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS['bg_darkest']};
}}
QWidget {{
    background-color: transparent;
    color: {COLORS['text_primary']};
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}}
QFrame#sidebar {{
    background-color: {COLORS['bg_dark']};
    border-right: 1px solid {COLORS['border']};
    border-radius: 8px;
}}
QFrame#card {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    padding: 16px;
}}
QPushButton {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: 600;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['border_light']};
}}
QPushButton#startBtn {{
    background-color: {COLORS['accent_green']};
    border: none;
    color: white;
    font-size: 14px;
}}
QPushButton#startBtn:hover {{
    background-color: #5cb85c;
}}
QPushButton#stopBtn {{
    background-color: {COLORS['accent_red']};
    border: none;
    color: white;
    font-size: 14px;
}}
QPushButton#stopBtn:hover {{
    background-color: #ff6659;
}}
QLineEdit, QComboBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 8px 12px;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {COLORS['accent_primary']};
}}
QTextEdit {{
    background-color: {COLORS['bg_dark']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    padding: 8px;
}}
"""

# ==================== THREAD LUỒNG CHẠY BOT ====================
class BotWorker(QThread):
    # Định nghĩa các tín hiệu giao tiếp giữa luồng chạy và giao diện
    log_signal = Signal(str)
    finished_signal = Signal()
    
    def __init__(self, mode, device_address, loop_count, discord_webhook_url=""):
        super().__init__()
        self.mode = mode
        self.device_address = device_address
        self.loop_count = loop_count
        self.discord_webhook_url = discord_webhook_url
        self.bot = None
        
    def run(self):
        # Thiết lập biến toàn cục cho luồng hoạt động
        import gbf_bot_prototype
        import builtins
        
        # Ghi đè hàm print trong luồng bot để xuất log ra giao diện GUI
        def custom_print(*args, **kwargs):
            msg = " ".join(map(str, args))
            self.log_signal.emit(msg)
            
        gbf_bot_prototype.print = custom_print
        
        try:
            # Kết nối thiết bị qua adbutils (tạo device object cho screenshot/tap nhanh)
            connect_device(self.device_address)
            
            self.bot = GBFController(mode=self.mode, discord_webhook_url=self.discord_webhook_url)
            # Khởi chạy luồng tuần tự
            custom_print(f"[BOT] Bắt đầu khởi tạo ADB tới: {self.device_address or 'Mặc định'}")
            
            # Khởi chạy vòng lặp
            self.bot.start_loop(loop_count=self.loop_count)
            
        except Exception as e:
            custom_print(f"[ERROR] Phát hiện ngoại lệ khi chạy Bot: {e}")
        finally:
            # Khôi phục lại hàm print mặc định để tránh giữ reference tới worker đã dừng/bị xóa
            gbf_bot_prototype.print = builtins.print
            self.finished_signal.emit()

    def stop(self):
        if self.bot:
            self.bot.is_running = False

# ==================== GIAO DIỆN CHÍNH (GUI) ====================
class GBFAutomationGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GBF ADB Automation Controller")
        self.resize(900, 600)
        self.setStyleSheet(MAIN_STYLESHEET)
        
        self.worker = None
        self._create_ui()
        self.add_log("Giao diện điều khiển khởi tạo thành công!")
        # Tự động quét và kết nối giả lập khi mở ứng dụng giống UMAT
        self.auto_detect_and_connect_adb()

    def _create_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # -------------------- PANEL BÊN TRÁI: CÀI ĐẶT --------------------
        left_panel = QFrame()
        left_panel.setObjectName("sidebar")
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(16)
        
        # Tiêu đề Panel
        lbl_title = QLabel("CÀI ĐẶT BOT GBF")
        lbl_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        lbl_title.setStyleSheet(f"color: {COLORS['accent_primary']};")
        left_layout.addWidget(lbl_title)
        
        # Cấu hình cổng ADB
        left_layout.addWidget(QLabel("Cổng kết nối ADB (Device Address):"))
        
        adb_row = QHBoxLayout()
        self.txt_adb = QLineEdit()
        self.txt_adb.setPlaceholderText("Ví dụ: 127.0.0.1:5555")
        self.txt_adb.setText("127.0.0.1:5555")  # Mặc định thông thường
        
        self.btn_auto_adb = QPushButton("Dò tìm")
        self.btn_auto_adb.setFixedWidth(70)
        self.btn_auto_adb.clicked.connect(self.auto_detect_and_connect_adb)
        
        adb_row.addWidget(self.txt_adb)
        adb_row.addWidget(self.btn_auto_adb)
        left_layout.addLayout(adb_row)
        
        # Chế độ chạy
        left_layout.addWidget(QLabel("Chế độ chiến đấu (Farming Mode):"))
        self.cb_mode = QComboBox()
        self.cb_mode.addItems([
            "Full Auto + Reload (full_auto)",
            "Full Auto + Instant Reload (full_auto_quick)",
            "Auto Spam Attack (auto)"
        ])
        left_layout.addWidget(self.cb_mode)
        
        # Cấu hình số vòng lặp
        left_layout.addWidget(QLabel("Cấu hình vòng lặp (Loop Settings):"))
        self.cb_loop_type = QComboBox()
        self.cb_loop_type.addItems(["Vô hạn (Indefinite)", "Giới hạn số lần (Limited count)"])
        self.cb_loop_type.currentIndexChanged.connect(self.on_loop_type_changed)
        left_layout.addWidget(self.cb_loop_type)
        
        self.lbl_loop_count = QLabel("Số vòng lặp:")
        self.lbl_loop_count.setVisible(False)
        self.txt_loop_count = QLineEdit()
        self.txt_loop_count.setText("10")
        self.txt_loop_count.setPlaceholderText("Nhập số vòng lặp, vd: 10")
        self.txt_loop_count.setVisible(False)
        left_layout.addWidget(self.lbl_loop_count)
        left_layout.addWidget(self.txt_loop_count)
        
        # Trạng thái kết nối ADB thử
        self.btn_check_adb = QPushButton("Kiểm tra kết nối ADB")
        self.btn_check_adb.clicked.connect(self.check_adb_connection)
        left_layout.addWidget(self.btn_check_adb)
        
        # Cấu hình Discord Webhook
        left_layout.addWidget(QLabel("Discord Webhook (Thông báo Captcha):"))
        webhook_row = QHBoxLayout()
        self.txt_webhook = QLineEdit()
        self.txt_webhook.setPlaceholderText("Nhập URL Discord Webhook (tùy chọn)")
        self.btn_save_webhook = QPushButton("Lưu")
        self.btn_save_webhook.setFixedWidth(70)
        self.btn_save_webhook.clicked.connect(self.save_webhook_config)
        webhook_row.addWidget(self.txt_webhook)
        webhook_row.addWidget(self.btn_save_webhook)
        left_layout.addLayout(webhook_row)
        
        # Đọc cấu hình khi khởi tạo GUI
        self.load_webhook_config()

        left_layout.addStretch()
        
        # Nút START / STOP
        self.btn_control = QPushButton("BẮT ĐẦU BOT")
        self.btn_control.setObjectName("startBtn")
        self.btn_control.setMinimumHeight(45)
        self.btn_control.clicked.connect(self.toggle_bot)
        left_layout.addWidget(self.btn_control)
        
        main_layout.addWidget(left_panel)
        
        # -------------------- PANEL BÊN PHẢI: LOG HOẠT ĐỘNG --------------------
        right_panel = QFrame()
        right_panel.setObjectName("card")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
        # Tiêu đề Panel Log
        lbl_log = QLabel("NHẬT KÝ HOẠT ĐỘNG (REAL-TIME LOG)")
        lbl_log.setFont(QFont("Segoe UI", 11, QFont.Bold))
        right_layout.addWidget(lbl_log)
        
        # Khung văn bản Log
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        right_layout.addWidget(self.txt_log)
        
        # Nút xóa màn hình Log
        btn_clear_log = QPushButton("Xóa nhật ký")
        btn_clear_log.setFixedWidth(100)
        btn_clear_log.clicked.connect(self.txt_log.clear)
        right_layout.addWidget(btn_clear_log)
        
        main_layout.addWidget(right_panel, stretch=1)

    # -------------------- HÀNH ĐỘNG GIAO DIỆN --------------------
    def add_log(self, text):
        """Thêm văn bản vào khung nhật ký log."""
        timestamp = time.strftime("[%H:%M:%S]")
        self.txt_log.append(f"{timestamp} {text}")
        
    def auto_detect_and_connect_adb(self):
        """Tự động quét các cổng giả lập phổ biến và kết nối ADB giống UMAT."""
        self.add_log("Bắt đầu quét tìm giả lập Android đang chạy...")
        common_ports = [5555, 5557, 5559, 7555, 16384, 16416, 62001, 62025, 21503]
        import subprocess
        
        found_device = None
        
        # 1. Quét thử các thiết bị đã kết nối sẵn
        adb_path = get_adb_path()
        try:
            res = subprocess.run([adb_path, "devices"], capture_output=True, text=True, timeout=2, shell=True)
            lines = res.stdout.strip().split("\n")
            for line in lines[1:]:
                if "\t" in line:
                    parts = line.split("\t")
                    if parts[1].strip() == "device":
                        found_device = parts[0]
                        self.add_log(f"Phát hiện thiết bị online sẵn: {found_device}")
                        break
        except Exception:
            pass
            
        # 2. Nếu chưa có, thử kết nối tới các cổng phổ biến
        if not found_device:
            for port in common_ports:
                addr = f"127.0.0.1:{port}"
                try:
                    subprocess.run([adb_path, "connect", addr], capture_output=True, text=True, timeout=0.8, shell=True)
                except Exception:
                    continue
            
            # Kiểm tra lại danh sách thiết bị sau khi thử connect
            try:
                res = subprocess.run([adb_path, "devices"], capture_output=True, text=True, timeout=2, shell=True)
                lines = res.stdout.strip().split("\n")
                for line in lines[1:]:
                    if "\t" in line:
                        parts = line.split("\t")
                        if parts[1].strip() == "device":
                            found_device = parts[0]
                            self.add_log(f"Kết nối tự động thành công tới: {found_device}")
                            break
            except Exception as e:
                self.add_log(f"[ERROR] Lỗi quét danh sách ADB: {e}")
                
        if found_device:
            self.txt_adb.setText(found_device)
            self.add_log(f"Đã tự động cấu hình thiết bị hoạt động: {found_device}")
        else:
            self.add_log("Không phát hiện giả lập Android nào. Vui lòng mở giả lập của bạn trước!")

    def check_adb_connection(self):
        """Thực thi kết nối và kiểm tra thiết bị qua ADB."""
        addr = self.txt_adb.text().strip()
        self.add_log(f"Đang thử kết nối tới ADB: {addr}...")
        
        import subprocess
        adb_path = get_adb_path()
        try:
            if addr:
                subprocess.run([adb_path, "connect", addr], capture_output=True, text=True, shell=True)
            res = subprocess.run([adb_path, "devices"], capture_output=True, text=True, shell=True)
            devices_list = res.stdout.strip()
            self.add_log(f"Danh sách thiết bị kết nối:\n{devices_list}")
            
            if addr in devices_list or (not addr and len(devices_list.split('\n')) > 1):
                QMessageBox.information(self, "Kết Nối", "Kết nối ADB thành công!", QMessageBox.Ok)
            else:
                QMessageBox.warning(self, "Kết Nối", "Không tìm thấy thiết bị kết nối. Vui lòng bật ADB trên giả lập.", QMessageBox.Ok)
        except Exception as e:
            self.add_log(f"[ERROR] Kiểm tra ADB lỗi: {e}")
            QMessageBox.critical(self, "Kết Nối", f"Lỗi ADB: {e}", QMessageBox.Ok)

    def on_loop_type_changed(self, index):
        """Ẩn/hiện ô nhập số vòng lặp khi đổi chế độ."""
        is_limited = (index == 1)
        self.lbl_loop_count.setVisible(is_limited)
        self.txt_loop_count.setVisible(is_limited)

    def load_webhook_config(self):
        """Đọc webhook từ file config.txt nếu có."""
        config_file = "config.txt"
        if os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    webhook = f.read().strip()
                    if webhook:
                        self.txt_webhook.setText(webhook)
            except Exception as e:
                self.add_log(f"[ERROR] Không thể đọc config.txt: {e}")

    def save_webhook_config(self):
        """Lưu webhook vào file config.txt."""
        config_file = "config.txt"
        webhook = self.txt_webhook.text().strip()
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                f.write(webhook)
            self.add_log("[INFO] Đã lưu Webhook URL vào config.txt")
            QMessageBox.information(self, "Lưu cấu hình", "Lưu Discord Webhook thành công!", QMessageBox.Ok)
        except Exception as e:
            self.add_log(f"[ERROR] Không thể lưu config.txt: {e}")
            QMessageBox.warning(self, "Lỗi lưu cấu hình", f"Không thể lưu file: {e}", QMessageBox.Ok)

    def toggle_bot(self):
        """Bật/tắt trạng thái luồng chạy của Bot."""
        if self.worker and self.worker.isRunning():
            # Yêu cầu dừng bot
            self.add_log("Đang yêu cầu dừng bot gracefully...")
            self.worker.stop()
            if not self.worker.wait(3000): # Đợi tối đa 3 giây để luồng dừng
                self.add_log("Bot không phản hồi dừng. Đang buộc tắt...")
                self.worker.terminate() # Buộc dừng luồng
                self.worker.wait()
            self.on_bot_stopped()
        else:
            # Lấy thông số loop
            loop_type_index = self.cb_loop_type.currentIndex()
            if loop_type_index == 0:
                loop_count = -1
            else:
                try:
                    loop_count = int(self.txt_loop_count.text().strip())
                    if loop_count <= 0:
                        raise ValueError()
                except ValueError:
                    QMessageBox.warning(self, "Cài đặt", "Vui lòng nhập số vòng lặp hợp lệ (> 0)!", QMessageBox.Ok)
                    return
            
            # Khởi chạy luồng bot mới
            mode_text = self.cb_mode.currentText()
            if "Instant" in mode_text or "quick" in mode_text:
                mode = "full_auto_quick"
            elif "Full Auto" in mode_text:
                mode = "full_auto"
            else:
                mode = "auto"
            device_address = self.txt_adb.text().strip()
            
            self.add_log(f"Khởi động bot (Chế độ: {mode.upper()}, Số vòng: {'Vô hạn' if loop_count == -1 else loop_count})...")
            
            # Vô hiệu hóa cấu hình đổi trong khi bot chạy
            self.txt_adb.setEnabled(False)
            self.cb_mode.setEnabled(False)
            self.cb_loop_type.setEnabled(False)
            self.txt_loop_count.setEnabled(False)
            self.btn_check_adb.setEnabled(False)
            self.txt_webhook.setEnabled(False)
            self.btn_save_webhook.setEnabled(False)
            
            # Cấu hình nút STOP
            self.btn_control.setText("DỪNG BOT")
            self.btn_control.setObjectName("stopBtn")
            self.btn_control.setStyleSheet(f"background-color: {COLORS['accent_red']};")
            
            webhook_url = self.txt_webhook.text().strip()
            if webhook_url: # Auto save when starting bot
                try:
                    with open("config.txt", "w", encoding="utf-8") as f:
                        f.write(webhook_url)
                except:
                    pass

            # Tạo luồng worker chạy ngầm
            self.worker = BotWorker(mode=mode, device_address=device_address, loop_count=loop_count, discord_webhook_url=webhook_url)
            self.worker.log_signal.connect(self.add_log)
            self.worker.finished_signal.connect(self.on_bot_stopped)
            self.worker.start()

    def on_bot_stopped(self):
        """Khôi phục lại trạng thái giao diện khi dừng bot."""
        self.add_log("Bot đã dừng hoạt động.")
        self.txt_adb.setEnabled(True)
        self.cb_mode.setEnabled(True)
        self.cb_loop_type.setEnabled(True)
        self.txt_loop_count.setEnabled(self.cb_loop_type.currentIndex() == 1)
        self.btn_check_adb.setEnabled(True)
        self.txt_webhook.setEnabled(True)
        self.btn_save_webhook.setEnabled(True)
        
        self.btn_control.setText("BẮT ĐẦU BOT")
        self.btn_control.setObjectName("startBtn")
        self.btn_control.setStyleSheet(f"background-color: {COLORS['accent_green']};")
        
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def closeEvent(self, event):
        """Xử lý tắt ứng dụng an toàn."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Xác nhận thoát", "Bot đang hoạt động. Bạn có chắc chắn muốn dừng bot và thoát không?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.terminate()
                self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    gui = GBFAutomationGUI()
    gui.show()
    sys.exit(app.exec())
