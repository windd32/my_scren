import ctypes
import ctypes.wintypes as wintypes
import os
import sys
import zlib
import struct
from datetime import datetime

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
WM_HOTKEY = 0x0312
VK_HOME = 0x24

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]

def get_app_folder():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def capture_active_window():
    hwnd = user32.GetForegroundWindow()
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))

    width = rect.right - rect.left
    height = rect.bottom - rect.top

    hdc_window = user32.GetWindowDC(hwnd)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
    hbitmap = gdi32.CreateCompatibleBitmap(hdc_window, width, height)
    gdi32.SelectObject(hdc_mem, hbitmap)
    gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_window, 0, 0, SRCCOPY)

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = width
    bmi.biHeight = -height
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(hdc_mem, hbitmap, 0, height, buffer, ctypes.byref(bmi), 0)

    gdi32.DeleteObject(hbitmap)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_window)

    return width, height, buffer.raw

def save_png(filename, width, height, pixel_data):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type
        row_start = y * width * 4
        for x in range(width):
            i = row_start + x * 4
            b = pixel_data[i]
            g = pixel_data[i + 1]
            r = pixel_data[i + 2]
            # Принудительно ставим альфу = 255 (исправление пропавшего белого)
            raw.extend([r, g, b, 255])

    compressed = zlib.compress(bytes(raw), 9)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")

    with open(filename, "wb") as f:
        f.write(png)

def take_screenshot():
    try:
        width, height, pixels = capture_active_window()
        folder = get_app_folder()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(folder, f"screenshot_{timestamp}.png")
        save_png(filename, width, height, pixels)
        print(f"[+] Сохранено: {filename}")
    except Exception as e:
        print(f"[!] Ошибка: {e}")

def main():
    print("Скриншотер запущен (PNG, белый цвет исправлен)")
    print("Нажми HOME — скриншот активного окна")
    print("Выход — Ctrl+C\n")

    if not user32.RegisterHotKey(None, 1, 0, VK_HOME):
        print("Не удалось зарегистрировать HOME. Запусти от имени администратора.")
        return

    msg = wintypes.MSG()
    try:
        while True:
            if user32.GetMessageA(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY and msg.wParam == 1:
                    take_screenshot()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageA(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        user32.UnregisterHotKey(None, 1)
        print("Завершено.")

if __name__ == "__main__":
    main()
