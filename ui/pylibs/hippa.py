# hippa.py - HippaFone helper library (part 1: screen words and radio) for the
# Adafruit ESP32-S3 Feather with the 3.5" TFT FeatherWing. Part 2 is hippa_io.py
# (button, light, keyboard, time). Part 3 is hippa_screen.py (draws on the
# screen). Copy all three files to the board as-is; do not edit them.
from machine import UART
import time, hippa_screen
from hippa_io import button_pressed, button_is_down, light, light_off, typed_line, wait, now

_s = {}   # everything the library remembers lives in this one box


def _display():
    # Sets up the screen the first time it is needed, then reuses it.
    if "tft" not in _s:
        _s["tft"] = hippa_screen.Screen()
        _s["title"] = ""
        _s["lines"] = []
        _s["shown"] = [""] * hippa_screen.ROWS   # what each row shows right now
    return _s["tft"]


def _redraw():
    # Draws the yellow title and the white body lines. Only rows that changed
    # are drawn, so the screen does not flicker.
    tft = _display()
    rows = [_s["title"][:30]] + _s["lines"]
    rows += [""] * (hippa_screen.ROWS - len(rows))
    for i in range(hippa_screen.ROWS):
        if rows[i] != _s["shown"][i]:
            tft.line(i, rows[i], hippa_screen.YELLOW if i == 0 else hippa_screen.WHITE)
            _s["shown"][i] = rows[i]


def screen_title(text):
    # Sets the title on the top line of the screen.
    _display()
    _s["title"] = str(text)
    _redraw()


def screen_write(text):
    # Adds a line under the title; long text wraps, old lines scroll away.
    _display()
    text = str(text)
    while True:
        _s["lines"].append(text[:30])
        text = text[30:]
        if not text:
            break
    _s["lines"] = _s["lines"][1 - hippa_screen.ROWS:]
    _redraw()


def screen_clear():
    # Erases the body lines but keeps the title.
    _display()
    _s["lines"] = []
    _redraw()


def _uart():
    # Opens the serial wire to the radio the first time it is needed.
    if "uart" not in _s:
        _s["uart"] = UART(1, 38400, tx=39, rx=38, timeout=50, rxbuf=1024)
        _s["buf"] = bytearray()
        _s["last"] = 0
    return _s["uart"]


def _text(buf):
    # Turns raw bytes into a plain text string, dropping odd bytes.
    return "".join([chr(b) for b in buf if 32 <= b < 127 or b == 9]).strip()


def radio_message():
    # Returns one whole message from the radio, or "" if none is ready yet.
    data = _uart().read()
    buf = _s["buf"]
    if data:
        buf.extend(data)
        _s["last"] = time.ticks_ms()
    msg = None
    n = buf.find(b"\n")
    if n >= 0:
        msg = _text(buf[:n])
        _s["buf"] = bytearray(buf[n + 1:])
    elif len(buf) > 0 and time.ticks_diff(time.ticks_ms(), _s["last"]) > 300:
        msg = _text(buf)
        _s["buf"] = bytearray()
    if msg:
        print("RX: " + msg)
        return msg
    return ""


def radio_send(text):
    # Sends your text over the radio (up to 200 bytes, no line ending added).
    text = str(text)
    _uart().write(text.encode()[:200])
    print("TX: " + text)
