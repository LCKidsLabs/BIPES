# hippa_io.py - HippaFone helper library (part 2: button, light, keyboard,
# time) for the Adafruit ESP32-S3 Feather. hippa.py imports this file.
# Copy all three files to the board as-is; do not edit them.
from machine import Pin
import time, sys, select, neopixel

_s = {}   # everything this file remembers lives in this one box


def _update():
    # Updates the BOOT button's steady state; returns True if it just became pressed.
    if "btn" not in _s:
        _s["btn"] = [Pin(0, Pin.IN, Pin.PULL_UP), False, 0]   # pin, steady state, change time
    b = _s["btn"]
    down = b[0].value() == 0   # the BOOT button reads 0 while it is held down
    if down != b[1] and time.ticks_diff(time.ticks_ms(), b[2]) > 30:
        b[1] = down
        b[2] = time.ticks_ms()
        return down
    return False


def button_pressed():
    # True one time each time you press the BOOT button.
    return _update()


def button_is_down():
    # True while the BOOT button is held down.
    _update()
    return _s["btn"][1]


def _pixel():
    # Sets up the one colour light the first time it is needed.
    if "px" not in _s:
        Pin(21, Pin.OUT, value=1)
        _s["px"] = neopixel.NeoPixel(Pin(33), 1)
    return _s["px"]


def _clamp(v):
    # Keeps a colour number between 0 and 255.
    return max(0, min(255, int(v)))


def light(r, g=None, b=None):
    # Turns the light on: light(255, 0, 0) or light("#ff0000").
    if isinstance(r, str):
        h = r.strip().lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    np = _pixel()
    np[0] = (_clamp(r), _clamp(g or 0), _clamp(b or 0))
    np.write()


def light_off():
    # Turns the light off.
    light(0, 0, 0)


def typed_line():
    # Returns a line typed in the USB console, or "" if none is finished.
    if "poll" not in _s:
        _s["poll"] = select.poll()
        _s["poll"].register(sys.stdin, select.POLLIN)
        _s["typed"] = ""
    while _s["poll"].poll(0):
        c = sys.stdin.read(1)
        if c == "\n":
            line = _s["typed"].strip()
            _s["typed"] = ""
            return line
        if c != "\r":
            _s["typed"] += c
    return ""


def wait(seconds):
    # Pauses for this many seconds.
    time.sleep(seconds)


def now():
    # Seconds since the board started, as a decimal number.
    return time.ticks_ms() / 1000.0
