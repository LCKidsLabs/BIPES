# hippa_screen.py - HippaFone helper library (part 3: the screen) for the
# 3.5" TFT FeatherWing on the Adafruit ESP32-S3 Feather. hippa.py imports this
# file. Copy all three files to the board as-is; do not edit them.
from machine import Pin, SPI
import framebuf, struct, time

COLS, ROWS = 30, 20    # letters across and rows down; each letter is 16 x 16 pixels
WHITE, YELLOW = 0xFFFF, 0xFFE0

# Start-up commands for the screen chip (HX8357), from Adafruit's adafruit_hx8357
# library: command, number of data bytes (+128 if a wait follows), the data, then
# the wait in ms (255 means 500 ms).
_INIT = (
    b"\x01\x80\x64"
    b"\xb9\x83\xff\x83\x57\xff"
    b"\xb3\x04\x80\x00\x06\x06"
    b"\xb6\x01\x25"
    b"\xb0\x01\x66"
    b"\xcc\x01\x05"
    b"\xb1\x06\x00\x15\x1c\x1c\x83\xaa"
    b"\xc0\x06\x50\x50\x01\x3c\x1e\x08"
    b"\xb4\x07\x02\x40\x00\x2a\x2a\x0d\x78"
    b"\xe0\x22\x02\x0a\x11\x1d\x23\x35\x41\x4b\x4b\x42\x3a\x27\x1b\x08\x09\x03\x02\x0a"
    b"\x11\x1d\x23\x35\x41\x4b\x4b\x42\x3a\x27\x1b\x08\x09\x03\x00\x01"
    b"\x3a\x01\x55"
    b"\x36\x01\xc0"
    b"\x35\x01\x00"
    b"\x44\x02\x00\x02"
    b"\x11\x80\x96"
    b"\x36\x01\xa0"
    b"\x29\x80\x32"
)


class Screen:
    def __init__(self):
        Pin(7, Pin.OUT, value=1)    # power for the touch chip and the STEMMA QT port
        Pin(5, Pin.OUT, value=1)    # the microSD slot shares the wires: keep it unselected
        self.cs = Pin(9, Pin.OUT, value=1)
        self.dc = Pin(10, Pin.OUT, value=1)
        # Never go above 24 MHz: at 40 MHz this screen stays white.
        self.spi = SPI(1, baudrate=24000000, sck=Pin(36), mosi=Pin(35), miso=Pin(37))
        self.small = framebuf.FrameBuffer(bytearray(30 * 8), 240, 8, framebuf.MONO_HLSB)
        self.row = bytearray(480 * 16 * 2)
        self.big = framebuf.FrameBuffer(self.row, 480, 16, framebuf.RGB565)
        i = 0
        while i < len(_INIT):
            c, n = _INIT[i], _INIT[i + 1]
            i += 2
            self._send(c, _INIT[i:i + (n & 127)])
            i += n & 127
            if n & 128:
                time.sleep_ms(500 if _INIT[i] == 255 else _INIT[i])
                i += 1
        for r in range(ROWS):
            self.line(r, "", WHITE)

    def _send(self, command, data=b""):
        # Sends one command and its data to the screen chip.
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes((command,)))
        if data:
            self.dc(1)
            self.spi.write(data)
        self.cs(1)

    def line(self, row, text, color):
        # Draws one whole row. The built-in 8 x 8 letters are drawn twice as big.
        text = text[:COLS]
        self.small.fill(0)
        self.small.text(text, 0, 0, 1)
        self.big.fill(0)
        c = ((color & 255) << 8) | (color >> 8)   # the screen wants the high byte first
        for y in range(8):
            for x in range(8 * len(text)):
                if self.small.pixel(x, y):
                    self.big.fill_rect(x * 2, y * 2, 2, 2, c)
        y = row * 16
        self._send(0x2A, struct.pack(">HH", 0, 479))     # which columns
        self._send(0x2B, struct.pack(">HH", y, y + 15))  # which rows
        self._send(0x2C, self.row)                       # the pixels
