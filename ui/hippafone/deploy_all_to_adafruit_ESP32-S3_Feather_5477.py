#!/usr/bin/env python3
# MIT License
#
# Copyright (c) 2026 Elizavetta (Leeza) Gay
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Third-party parts this script carries or downloads, and their licences. The licence texts are
# written to the Feather's /licenses folder; "python <this script> --licenses" says which file
# is covered by which licence.
#   TinyUF2 bootloader 0.36.0 (downloaded, written to the flash) ... MIT, Ha Thach / Adafruit
#   MicroPython 1.29.0 firmware (downloaded, written to the flash) .. MIT, Damien P. George and others
#   sdcard.py from micropython-lib (downloaded) ..................... MIT, micropython-lib contributors
#   hf_sd_fast.py (adapted from micropython-lib's sdcard.py) ........ MIT, micropython-lib contributors
#   hf_panel_init.py (init tables from adafruit_hx8357 and
#       st7789py_mpy) ............................................... MIT, Adafruit / Russ Hughes
#   hf_font.py (Terminus Font 6x12 bitmaps) ......................... SIL Open Font License 1.1
#   hf_gif.mpy (AnimatedGIF decoder by Larry Bank / BitBank
#       Software, MicroPython's native-module glue) ................. Apache-2.0 and MIT
#   Everything else in this script and on the Feather (hf_*.py, hippa.py,
#       hf_settings.py, the wrapper of hf_gif.mpy) .................. MIT, Elizavetta (Leeza) Gay
"""Get an Adafruit ESP32-S3 Feather (product 5477) ready for HippaFone block programming.

Needs Python 3.10 or newer and nothing else: no pip packages, no other files. For Windows 11 and
Ubuntu 22.04 to 26.04 LTS. One file: copy it anywhere and run it.

    python deploy_all_to_adafruit_ESP32-S3_Feather_5477.py                 everything that is needed
    python deploy_all_to_adafruit_ESP32-S3_Feather_5477.py --rotation 0    USB-C on the left (without it a new board gets 180)
    python deploy_all_to_adafruit_ESP32-S3_Feather_5477.py --reflash       put MicroPython on again anyway
    python deploy_all_to_adafruit_ESP32-S3_Feather_5477.py --list          show the boards and ports it sees
    python deploy_all_to_adafruit_ESP32-S3_Feather_5477.py --licenses      say which licence covers which file
    python deploy_all_to_adafruit_ESP32-S3_Feather_5477.py --save-libraries DIR   write the files into a folder

What it does:
1. MicroPython. If the Feather does not already run MicroPython 1.29.0, the script downloads it
   (micropython.org, checked against a fixed SHA-256) and tells you how to put the Feather in
   download mode, then watches until it really is in one before it goes on:
     - double-tap RESET: the TinyUF2 bootloader opens a drive called FTHRS3BOOT. The script copies
       MicroPython's .uf2 file onto it.
     - hold BOOT, press and let go of RESET, let go of BOOT: the chip's own ROM download mode (a
       new COM port, USB 303A:1001). The script talks to the ROM loader itself (no esptool): it puts
       the TinyUF2 bootloader 0.36.0 back first if it is missing or a different one, writes
       MicroPython into the app slot at 0x10000, checks both with the chip's MD5, then restarts it.
2. The libraries. Every library the finished HippaFone program uses goes on the Feather (not the
   program itself, main.py, nor its pictures): hf_display, hf_text, hf_font, hf_touch, hf_mesh,
   hf_ble_kb, hf_pictures, hf_gif.mpy, hf_bmp, hf_sd, hf_sd_fast, hf_panel_init, hf_battery,
   hf_cardkb, hf_settings and micropython-lib's sdcard.py. All of them except sdcard.py are inside
   this script. hf_settings.py is made for this Feather: its own values are kept unless --rotation
   says otherwise.
3. The block helper. It writes hippa.py, the file that programs made with the blocks at
   https://bipes.arrowcircuits.com/ui/ import, onto the Feather. The older helper files
   hippa_io.py and hippa_screen.py are removed. Nothing else on the Feather is touched: the phone
   itself is built with the blocks.
4. The licences. The licence texts of everything above go into /licenses on the Feather, with a
   README.txt that says which licence covers which file.

Other people's files always come from their own homes, downloaded with Python's urllib (like
curl) and checked against a fixed SHA-256: MicroPython from micropython.org, TinyUF2 from
Adafruit's tinyuf2 releases on GitHub, sdcard.py from the micropython-lib repo on GitHub (commit
446038d). They are kept in %LOCALAPPDATA%\\HippaFone\\cache or ~/.cache/hippafone.

--save-libraries DIR writes every file the script would put on the Feather (libraries, hippa.py,
hf_settings.py with its default values, DIR/licenses) into a folder, without touching a board;
sdcard.py comes along only if it is in the cache or can be downloaded.

Every file is written as <name>.tmp, its SHA-256 checked on the Feather, then renamed; files that
are already the same are skipped.

Close anything else using the Feather's port first (a BIPES tab, Thonny, mpremote, a serial
terminal). On Ubuntu your user must be in the dialout group (sudo usermod -aG dialout $USER, then
log out and back in), and the FTHRS3BOOT drive must be open in the Files app to be written.
"""
from __future__ import annotations

import argparse
import ast
import base64
import glob
import hashlib
import io
import os
import re
import string
import struct
import sys
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("This needs Python 3.10 or newer; this is Python %d.%d." % sys.version_info[:2])

MICROPYTHON_ID = (0x303A, 0x4001)     # MicroPython running on an ESP32-S3 (its own USB)
ROM_ID = (0x303A, 0x1001)             # ESP32-S3 ROM download mode (USB serial/JTAG)
MP_VERSION = "1.29.0"
BIPES_URL = "https://bipes.arrowcircuits.com/ui/"
# Other people's files, always downloaded from their own home and checked against a fixed
# SHA-256: name -> (url, sha256).
DOWNLOADS = {
    "micropython.uf2": (
        "https://micropython.org/resources/firmware/ESP32_GENERIC_S3-20260824-v1.29.0.uf2",
        "767af3709fcbe49d469dcc97caa8bba7a0f4ad3ba2d2c48628192b685dbadbaf"),
    "micropython.app-bin": (
        "https://micropython.org/resources/firmware/ESP32_GENERIC_S3-20260824-v1.29.0.app-bin",
        "6d03197a2f6cc796801cb547300417fca4e2db60429d4b709c64f0645a412ee6"),
    "tinyuf2.zip": (                    # Adafruit's TinyUF2 0.36.0 release for the Feather ESP32-S3
        "https://github.com/adafruit/tinyuf2/releases/download/0.36.0/tinyuf2-adafruit_feather_esp32s3-0.36.0.zip",
        "108d98630dc3daefa9a3fa385ee3ad06f6dc268e063ae26cd0e4c2b1549c9d77"),
    "sdcard.py": (                      # micropython-lib (MIT), commit 446038d "sdcard: Compute CRC7 ..."
        "https://raw.githubusercontent.com/micropython/micropython-lib/"
        "446038da9b03ad2aa67e256134937e19ff8d0a73/micropython/drivers/storage/sdcard/sdcard.py",
        "515a33617c0e956f63a351a87b284881ebaf808069b104d6b354f2b83aba7204"),
}
# TinyUF2 0.36.0 for the 5477 (its flash_args) and MicroPython's place in its partition table:
# ota_0 (2816 KB) at 0x10000, TinyUF2 itself at 0x2D0000, the files (ffat) at 0x310000.
TINYUF2_PARTS = ((0x0, "bootloader.bin"), (0x8000, "partition-table.bin"),
                 (0xE000, "ota_data_initial.bin"), (0x2D0000, "tinyuf2.bin"))
APP_OFFSET = 0x10000
# The libraries of the finished HippaFone program (what main.py imports), without main.py itself.
# hf_settings.py is made for each Feather from the template below; sdcard.py is in DOWNLOADS.
LIBRARIES = ("hf_display.py", "hf_text.py", "hf_font.py", "hf_touch.py", "hf_mesh.py", "hf_ble_kb.py",
             "hf_pictures.py", "hf_gif.mpy", "hf_bmp.py", "hf_sd.py", "hf_panel_init.py",
             "hf_sd_fast.py", "hf_battery.py", "hf_cardkb.py")
SETTINGS = "hf_settings.py"
HELPER = "hippa.py"
OLD_HELPERS = ("hippa_io.py", "hippa_screen.py")     # the one hippa.py replaces them
LICENSE_DIR = "licenses"                            # on the Feather: /licenses
USER_AGENT = "hippafone-setup"
CHUNK = 8192                                        # file bytes per command to MicroPython
ROTATIONS = (0, 90, 180, 270)
DEFAULT_ROTATION = 180          # a Feather with nothing on it yet: USB-C on the right

# ------------------------------------------------------------------------------------------------
# The files this script carries. Each sits between BEGIN CARRIED / END CARRIED comments and is
# stored as zlib-compressed, base64-encoded text (or, for the binary hf_gif.mpy and the font table,
# plain base64), so no content can break the Python string. A maintainer tool in the HippaFone
# source repository rewrites these blocks; do not edit them by hand.
_PACKED = {}

# --- BEGIN CARRIED hf_display.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 6457 bytes, SHA-256 2347e3a4f783959190421b859934370ac1aa9477da2e350da64a18e9c2138d73.
_PACKED["hf_display.py"] = (
    "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"
    "jLq/c4Hnurv8D++eI5k="
)
# --- END CARRIED hf_display.py ---

# --- BEGIN CARRIED hf_text.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 5051 bytes, SHA-256 9e8e22833cac83541e174dc40b830bf1b9708c831500bcde8839d783b79b3067.
_PACKED["hf_text.py"] = (
    "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"
)
# --- END CARRIED hf_text.py ---

# --- BEGIN CARRIED hf_touch.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 2090 bytes, SHA-256 8704460386609e6d1246e9bda0a5e227a9aebb295e464526a27648a3714639e1.
_PACKED["hf_touch.py"] = (
    "eNq1Vdtu2zgQfddXDBy0lQBZVeSkSd2mQJDEbYAmKGJlt0BgCLRExQRkUiDp2Orl3zskY1nqei8vqwdfyDO3c2ZG"
    "BzD9cvl1+JnllCs6vC4o16xkVI7h5jr1DuBC1I1kjwsNfh5AEidv4Kpi38gT1ZqA/5nSbySAj6RB7CdW12QiOI3A"
    "OswpaLrRIDjoBYW5ILIYw+vKBVOvMcJwZ6M32hsMBpP0eDR6AzmpSc40e0IfYpUvIBdcS1FVVIIorb9RdDyANeOP"
    "4F8nFxBvRqdB5HkpXkmqmLLG5v6VgnR6kcTxCfjx5ug0AKaACw21kJpiShzjmzPGYUF4gRExcaWB6cik5Hnnl5d3"
    "cGZDeFjoHVmjLeNIit6EoJtgm9MuSwxq3EvCNIwSEzaGUpIlheEHULmklEPNNrQKocaa9Epy8Av6iBcqCDGIcacM"
    "3lwpIAoWZVYwVVekif68vv2Ypfd3t9MIbihRK0kLwzPpiOBlN+dfppj2dw/wicdQkeW8IOByHmPyTQijw7cwxCOM"
    "aVBv98FcjQ5weLoHcXRinaC71lFysge3DRbC1gLRPz3PyyuiFDjtx9a+oCVkGeNMZ5mvaFWGwJI8hJWaZ4JntifP"
    "JqRSNHAG5jG4CGFYNH72j7uGeN/92wdaKc5MocDKHg4ohoO4D5+vSkTPG02JlKTxjwOvLUBRnUmhiWaCPxdhvHcy"
    "xva6R59GbNsNsCR1bXoaG2qnNzZTz5VzAnGIeoU2UyEN46HL8A9SreiVlEJGpn23sbAaW5tpfWx12x67TMyD3doz"
    "9wfbkPBCWju1qt3UDOAF2DzCINjLn/n6RwUczhK9Y0yLzPLwzJYk62zjvhrH3dkt9nafwPRfB88NK44Q+W302iFb"
    "kwZWdX/K2hi+2SJZTTjqs2Z6sTPrlhQaEboyBZGrUTxRKVlBVYefErFm6+SkqvaKhOvIVNrX55na1k17Sav/X1xJ"
    "bQDr+cH8nPldeTptLykprIB9nUw9jj8uoERKce8VYs2fu9Z3R6qvertaSyZxJTtMaErEw9b7f9i779reMjOGy17b"
    "PW+UtC3RU6HYsozT/ZftEpn6SimW2ZIucUVp4ZsXRIjvhzgJodhRZsQqHuJZV13b83ZgOXyA4zH83XMA6WU2Tc/T"
    "+6llVKH/yWQfgX2ZnUyG7N+lQ6Z9v3g4nMFLk+skgPfvAV+HPzDJZOYuR/suj2beL17sbhM="
)
# --- END CARRIED hf_touch.py ---

# --- BEGIN CARRIED hf_mesh.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 15883 bytes, SHA-256 274e8f98dd2e392957f5013be4b14754772ed87abba789bf8919b8b80386644c.
_PACKED["hf_mesh.py"] = (
    "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"
    "/wdFlS7w"
)
# --- END CARRIED hf_mesh.py ---

# --- BEGIN CARRIED hf_ble_kb.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 16847 bytes, SHA-256 51f1b6c49865d4f728316d8270a77355dcfdae4616765f5954b433c0332e5cc0.
_PACKED["hf_ble_kb.py"] = (
    "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"
)
# --- END CARRIED hf_ble_kb.py ---

# --- BEGIN CARRIED hf_pictures.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 5049 bytes, SHA-256 1abdd089b33424ede20794f9b1bd4a359f505c5c3d688ba40a4bccdcbb556e15.
_PACKED["hf_pictures.py"] = (
    "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"
    "/wM9mt9K"
)
# --- END CARRIED hf_pictures.py ---

# --- BEGIN CARRIED hf_bmp.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 3286 bytes, SHA-256 b28694eda692a8027a4c5c73ec3d67dd16555da0a043d234c6b37cf2a23d97dd.
_PACKED["hf_bmp.py"] = (
    "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"
)
# --- END CARRIED hf_bmp.py ---

# --- BEGIN CARRIED hf_sd.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 1757 bytes, SHA-256 a77f58abca1778220c92215d624b4143f4409ec606630384a1dcdb5b21888320.
_PACKED["hf_sd.py"] = (
    "eNqNVGFv0zwQ/p5fcW/34XVQl6UTRVDUD6ilUIlp01oQEqDKTS6rtdSObGdt9us5202zMhBYleLad/c899ydz2Bx"
    "M/16/klkKA2ez3OUVhQC9Qiu5svoDCaqarS421hgWQyX6eUreF+KR/6A1nJgnxAfeQwfeEO2H0VV8ZmSmIAPmCFY"
    "3FtQEuwGYa24zkdwUQYwc0EI552P3duo1+ttRabVYgoiOO2EvPvfgCmVHYHZcI3Gn+fCVCVv6GpxM4d1bfowWTik"
    "Dzfz6yGw6TBOoqgic8qIxVBptSbXnbAbmFxNU1hjoTSCyTNilSymE/qAMBRKlPZtMJQK3C0cbjUXRBuuF++1Vrof"
    "cZkTF/K5R6yMw9+QUhCOjxQdOagNX5cISFFRw443SYtcNcB8zlVjN0qel2IdE2pZmshUIhFSWLbmda65xXGSJDEI"
    "a7As+mCUh3G2FJMytapVx0HywqLeEYQBtilWBzbJwW5FwUkhEjwS20ppqpKJCq22sOXZRkiEw/GNkFFEqY1hGEVR"
    "jgW0oroIowhoUZSlrsmlAB4U49LsUJsgNbtTIPIS47YTfB1zx5I6BamXnrC2cDlM4f7jY+K4ueiZIXCiwSaLvvsm"
    "15+XfXjgZY3jQexNnitFQWiFW6ubwLM13Wlhka173/dF0YMXMEhj+MM6g9cpZKXK7tvmCVU+xssMO8D8Er2xaNi3"
    "dP8y7cPJb/9m+COOD9G9QD4wlRUKsSddJreTY0BNubtQXGvesEGHRN0LKzclmss7ZJRCl2PLRCPPhbSKaQc7m8Un"
    "FlQt/S39Af+N/eWpu8dGW2sZjMbOKB38XqLbwcgXOPrFc8ZLEw4LIalNn5SBZBvEfy5KfOi1VcGNXbmWWmUlN4Z1"
    "HXc6uV5CDm3G1E/USbmizpLK0vNBE0ojb3eIEipF0wXMIAINhsk9SHzsNz8F3UU7CDPaB7DoJMXjaWC8VXWYjT50"
    "zfgy9asjf+WsDuOrc3rFZu+W8KDKeotuBC5MnsBteG5Y+97A3BPxf2JXPWHJW1J+3agchaK2ea7d82nwwzp+4heY"
    "h2mLn6TQbkIM3GdYWVg2FXo6I/jrOqM3AVSZ01PVvXyuaqq2R5h/5BVIKJMEsWnzpTAzbpmzJ9Y90o9a6CcoQwoD"
)
# --- END CARRIED hf_sd.py ---

# --- BEGIN CARRIED hf_battery.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 1055 bytes, SHA-256 91841eede8cb02bee3e610fb9fcf997bddcb2d3ad360c236f5cb62eea34771b6.
_PACKED["hf_battery.py"] = (
    "eNq9UsFu2kAQvfsrnuBiNwZsNxCEkkMKNEUiShWqKFIUWYt3gJWMF62XAFE/vrvrGJoot0qdA1gz+968eTNNzH6O"
    "HltTkVFRUmvCqdBiIUgNcDv55TUxlJuDEsuVhp8FSKKkh3EuXtkLac3gT4leWYAbdjBvf4jNhn2XBbXhCDOCpr2G"
    "LKBXhLlkig/QyatmZcd0aJ0weq+9RqNxe/0YX0TnfcyZ1qQOWLLtkizHJBnC57Rg21wj2n/tBQNkK6ZMVRTYkDK0"
    "OkRGeY4XmWtWFexn2TbMnnc9Gt3jymG9+/FN+jAcT6cuESUw0UTcw1zoMsRFvx0nXWwfLDEyuS20g8zuhhXgHPgA"
    "WRmbMD9owm4lczopyuWuysedpNur857nZTkrS3yrBh14ls/MhzQVhdBp6peUL0KIJAvBOFdXVn9QvbNhy21TNYLM"
    "7/u0fW/y9s87Er91drx/8RhvhpWPEbREHEXwlZmYEw9CSIVWDLFwO6yWwSWVKKQGK8odKWduTabrSergRkattK2I"
    "8YWS63RNa/8oNMSbtSGS4AimfUYbjbvZWCmp3pMq0ltVGGHeh8xaFL4ZwLhm5uRP0TPOwJ/iZ3RgvT9D1O4GwckS"
    "dx2fGfLZFcFPDCgTa5aX/9MZd6f/7o3bqe9Xtlxeoh/gtzMnwJf64Dt2/TZcuz9Uzyj+"
)
# --- END CARRIED hf_battery.py ---

# --- BEGIN CARRIED hf_cardkb.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 1143 bytes, SHA-256 2d64536e2f7f1d1478f28bd6e26f77592a35ad974d49d59bd424be3ec52fd51f.
_PACKED["hf_cardkb.py"] = (
    "eNptU9tu2kAQfd+vGJEHbMkhxlWaCiUPxJgWhVwU89CqqdBiD7DCXVu7mwRS9d87Y3MJUUfW2jvXM2fGJ5A+DL6f"
    "jlWG2uLpKEft1Fyh6cHtaCJOIC6rjVGLpQMv8yEKo8+QFOpNvqBzErwx4pv04avckO83VVVyWGrsQJ0wQ3C4dlBq"
    "cEuEWSlN3oOzoilmz6jC6SHGrZ1otVq356mT2Qpicr65jjh4FMXg5TiXz4WDcH0+9HukRljhBrIyR6jQgEGZBxDC"
    "6xI16LI2KguvUjmlFx3KLER/MHiEqzqFSO4myeM0fgyg+RoPa0s4CPjsi+t+fJM+9OMkgEEyTiZJY/7C5gsKT+Na"
    "0b2uScrRUo/SgTRI1R1UhVQaKqO0k7MCoZ/Go1EA0tZUZEtpZObQNNel1LlF17aM2vMB1xVmznbETfIjpTJ/dmB7"
    "0HrSrQPk3X0PlhWz1g7y7kZg+XPdnbX+CiGIyhqBx+T5PQEkxM/kPTCYlwbkgWKv/aTbAbSfZvVJqdpAHh8a9APA"
    "wiLc8UCZck5t0D0bDdxLZ4GuqcrBXrbcYgA1h08RXF41xS6hG10cMvmEOSuktdulaBBzF9Op0spNp57FYh6AijKi"
    "OM/NFU962xkLmztkJS7pPFazP+n5dWwoV6QeSkbBcgIT84y0eLzWRBUBcvXW0cAWNHGp6bGvaMQeXm3lXO+gECv3"
    "73aXV5aa1/Vf04ffylpaVzbXvwt492liTGmohnqhJQupSA4HaHuWWZzZHAqxsNuu9w6jmZvyt7dvO4Cu/zP8tQ/B"
    "dYaVg23J41QfKDmybScc/oc/5kx88FuJfzlpSBI="
)
# --- END CARRIED hf_cardkb.py ---

# --- BEGIN CARRIED hippa.py ---
# ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay.
# Carried text: 37300 bytes, SHA-256 99904ab8f665ad654ad64fe772f04f314cb82eb2f90ec41e310ea764681fc4ce.
_PACKED["hippa.py"] = (
    "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"
    "9e0E+k9IHf8X5vMmIg=="
)
# --- END CARRIED hippa.py ---

# --- BEGIN CARRIED hf_settings.py ---
# Ours (HippaFone), MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay. The template of hf_settings.py:
# the script keeps a Feather's own values and rewrites USB_ON_RIGHT from --rotation.
# Carried text: 532 bytes, SHA-256 3c5a2bd2fe6e565bf8b28245b34e29e8d4e510cc09088c2661db9b8808f3ec28.
_PACKED["hf_settings.py"] = (
    "eNqFkMlOwzAQhu95il/tgVZqAgKJQxEXCrSVyiJaJG7V4EwSS8aObKfb0zMJFcuJnKLx9y8zfSyfb9/ShVZsA6fz"
    "nG3UhWY/xsN8lfQxcfXe67KKGKghzs/OL3Fn9IE2HCNhsGA+0BBT2gs703VN985yhs5QMSLvIpxFrBjvjnw+xqn5"
    "CgunkpD+aOIuJr1ebynG2pYBhfOd7JtA7V3p6SPDpCJbMggbMg2PWsxCSVP506LURpLdTyioJG2zJHld3qyfHtcv"
    "8+lsNca20qrClvZo6g4OyrM46TDCVsfq96wgJa2wd02WACvfMNC9Ly9OAsQ3naB2Poq43Vc4j+PdWirnghoTr1C5"
    "bServbaRcygKLEOTB+g4zPCsVWw8tw2cz4NkHT+yuezUSGEyBsJYkHdNNy1ZLH1b7J6M+P1XzHARs/bYfw6C626v"
    "5BPhA662"
)
# --- END CARRIED hf_settings.py ---

# --- BEGIN CARRIED hf_sd_fast.py ---
# Adapted from micropython-lib's sdcard.py (MIT, micropython-lib contributors):
# https://raw.githubusercontent.com/micropython/micropython-lib/446038da9b03ad2aa67e256134937e19ff8d0a73/micropython/drivers/storage/sdcard/sdcard.py
# upstream SHA-256 515a33617c0e956f63a351a87b284881ebaf808069b104d6b354f2b83aba7204 (commit 446038d).
# Carried text: 1536 bytes, SHA-256 83bf88f7cad5acce57cfdabba0e81ead4841b049279f4cb0a4e6bfdf89de45ab.
_PACKED["hf_sd_fast.py"] = (
    "eNqNU11v2koQffevmMJDbQls89GkoeKhTYgU3aapCpUqtRVa22NYYXutnQXCv7+za+oC/VD3AZn1zDlnzhx3Yf7x"
    "7kv/vUyxIuw/ZFgZmUvUE3h8WHhdeJuJ2mAGuVYllDLVqj6Ytar6hUxeElCWCp2F9QH8+d2tfdQoMlkZFUy4e21M"
    "TZMo0mIfrqRZb5MtoU5VZZgnTFUZnUBGF/DReHwVj15n4iaJRyIbCnF1jcNXV4PR+GZ0jYObPH+dxeJ6dAaSablD"
    "TREZpcUKo0Zh1AplVT4Tl9LAv+IHITfdMoGWq7Xh9gCG8WDUs7/jS1PATqdlsmV+sn1rUa2QJmDWCEaWGFKBWC9L"
    "8gcByMrdZ8KIvlEbrKBWRQGSQGOpdpj1gJQrcfdUy4pgW4NRDD2M+ThMYiAy7DyoHJa3j3fLxcPj7OnzAvxBHAdN"
    "zRsgLPKQMUBUWfPHcSbbHIRG2GBtrKJCpaIgO/SCiQubjZS147OxwlQjOVHs5wSiookOXW6v//7hdvZhPgvNs/E6"
    "nc5xAU1KYM9hAAE/wsKIwkCmeJBKGXAOQYJmj0dHKGQIT5a10uYYOs/z0kIQwb0g08D6ZyScQODTPQmpAyYYQElQ"
    "o+bdEXG4L+zvNQ6zvnuN+GnxNGcD043rSNiczdGDI/xs/nE0BP96BP+9iyh4w33GBcWtzI5IwNONXw1dQXiiRxq7"
    "BSAjDixISzKywtDhZpi39vi2qge8p+NM9rj9peTHQXtlEpie7/VnNW992gagvc6VhqXdubYp9V2iTjiOne1H7Zuk"
    "B/Hz/X1wViJzpv4af4fp1L6dTeC3p+uMBqfNu3yZMMemvcWC8ELGcdzBObUWkhCe5jOtlfY7Nuhqa2AvJFu5cvNp"
    "pFpxRDs/O8vdDzOybVke2Khlyd+bPuwk7r2TsQqsfGs7vJi653J34Y5DKndfJ23p91PPw72WBpetf+WuWeOvNX7S"
    "+fac550A/nS6kK4x3dC2/Eu39xe/flP9P1p+zrI="
)
# --- END CARRIED hf_sd_fast.py ---

# --- BEGIN CARRIED hf_panel_init.py ---
# Init tables copied from adafruit_hx8357 (MIT, Adafruit Industries), tag 2.0.4:
# https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_HX8357/2.0.4/adafruit_hx8357.py
# upstream SHA-256 8768676f6995251120620323c4f54e2ae02ba4d24f558028f2394fc8ff61ca51,
# and from st7789py_mpy (MIT, Russ Hughes), commit 7265925:
# https://raw.githubusercontent.com/russhughes/st7789py_mpy/7265925bd0c092e8105200d18b2dba9dfbc12c27/lib/st7789py.py
# upstream SHA-256 a071cfc56a32006b3ddefcc1b68e158fbd7674df6a363cac59ea7ce9510ed958.
# Carried text: 2693 bytes, SHA-256 3a5796f34076bbe6403d1edbbe1c1f50244169a6e641c7976b93b21f0651a863.
_PACKED["hf_panel_init.py"] = (
    "eNqdld1v4jgQwN/5K0bwcEEXwEn4lu6hQKVFKnvda+9uH5CQkxjia4ij2OyCtH/8jrGTBrp3R7eSCx2Pf/M9bcHT"
    "4+Jz54FHLJOss4xZpviWs2IKq+Vzo9VowebD53EwGG2WH5fPU9gWYg80ptviwNUmOeorFxKlcjnt9XZcJYewG4l9"
    "r9Tp3ZXKc15E+Pl4UonILBX5AA4/m41oCkrA2dDm6f7Tn/cf5/fAs2tz3fwEVIGiO/C7pNtvu9pXSHUMEXNhLvJT"
    "wXeJAidqg0+8CaxYyqWk8MBmKc2izt88TTndS9iKAkoHYZnFB6kKzmT37NeDIYJiRwUiA5UwCAUt4in0UpMx2UPT"
    "nWsH1VHpxD09j0bjST1xUmlJftrs89MPs1YcpEwOuwTBdV2MROz36OLIHw4m/qDtnh38z7B90sFfAfyBSPhwZv4w"
    "N8svNIMZS8WLCE+pfOGnd0ZfOnoOu9lsPtKMpVg3rmsUpkxCJHLOYpMCgZwC8kL8wyKFHr2wXAHNaaHs/aEA8TWD"
    "mMs8pSeIC/4FHzjJdmNFWP92t9G47EudH5rFLqQs26kEnG9AjmMCfAsUYqZJ4UkxLHiaiq8SeyaminbhPoul7jFs"
    "i1hGNGfgrO4W8+cHfH5H0M5lFZ3Kjn7uWvJe894U+Bd50QKb+WrxBE7Kw6q0Xd0FKc8wRd4k6PhegAYxgw0sgIlu"
    "YfLoXHVY+2cDvsga/AZOAysNYXN9JN4an6+Pw36zkoUTlAXr43ZrPgcj/b12jzLSN++IPkN9avdDw/UHNRkxsmFN"
    "L4qMjNT1PMtDfW+AJzJH+0Fp7a21OyDmaE6gdRl+H9d46CdB/4m/Pvatvz41h8Tr46imy/Sdb3QJ3nvI9FDHR9sB"
    "+tLHv/uhPagTaA6yvVDbxIN5I0H5/pX705xzXK8crafjHNTyFdhcR6QmG9i81mT9vvVLM/1L33QdJ8O3TEqaUPtp"
    "gRmR6evUVE/8icEEiG7rPjYTYNu4Ph71Hr4cpouZq5rUIeiji0aaLng+wYa+4acFMmUsx62iKkhgITciNCQTxR7/"
    "O5U7aS9iVuJmQ9fMD9Zk7N+CbVWc7SGLFMfdGolMFSItmcGdYWJ9MdZb/GyBN4SQKwm53q78yCrYzLcORvbo6ugG"
    "DP7N2RbkooiSa69mI9d21a3Ja8GO4gq65swMxx/fzvlr/vuqfD8nZUDmfSUvA/XOW+ryLjB3HrmS960v1/Kyqlec"
    "hbVNcYqod3l3b+/ichv6duPoqR7rkTDTpyf9vNlwQ3n43UOZN6pyoZOGYwG/Vlzvf7h6E2juyDL19rNbxGNvuJ2S"
    "63vvHwSe4T9jqVtWZBVn8v6pLCcAKe3Gd7gh2wo="
)
# --- END CARRIED hf_panel_init.py ---

# --- BEGIN CARRIED hf_font ROWS ---
# Terminus Font 6x12 (ter-u12n.bdf), Copyright (C) 2018 Dimitar Toshkov Zhekov, SIL Open Font License 1.1.
# Source of the bitmaps: https://raw.githubusercontent.com/adafruit/circuitpython/10.3.1/tools/fonts/ter-u12n.bdf
# The glyph table below (95 glyphs of 12 bytes, ASCII 32 to 126; ROWS of hf_font.py) is that BDF converted by
# HippaFone's own tool; make_font() writes hf_font.py around it. Table SHA-256 ad7dcc3b1d65d83e904f4333a1ed89389d79763e359d38c6bb46deb052e68abf.
_FONT_ROWS_B64 = (
    "AAAAAAAAAAAAAAAAAAAgICAgIAAgIAAAAFBQUAAAAAAAAAAAAABQUPhQUPhQUAAAAAAgcKigcCiocCAAAABIqFAQ"
    "IChUSAAAAAAgUFAgaJCQaAAAACAgIAAAAAAAAAAAAAAQIEBAQEAgEAAAAABAIBAQEBAgQAAAAAAAAFAg+CBQAAAA"
    "AAAAACAg+CAgAAAAAAAAAAAAAAAgIEAAAAAAAAAA+AAAAAAAAAAAAAAAAAAgIAAAAAAICBAQICBAQAAAAABwiJio"
    "yIiIcAAAAAAgYCAgICAgcAAAAABwiIgIECBA+AAAAABwiAgwCAiIcAAAAAAIGChIiPgICAAAAAD4gIDwCAiIcAAA"
    "AABwgIDwiIiIcAAAAAD4CAgQECAgIAAAAABwiIhwiIiIcAAAAABwiIiIeAgIcAAAAAAAACAgAAAgIAAAAAAAACAg"
    "AAAgIEAAAAAACBAgQCAQCAAAAAAAAPgAAPgAAAAAAAAAQCAQCBAgQAAAAABwiIgQIAAgIAAAAABwiJioqJiAeAAA"
    "AABwiIiI+IiIiAAAAADwiIjwiIiI8AAAAABwiICAgICIcAAAAADgkIiIiIiQ4AAAAAD4gIDwgICA+AAAAAD4gIDw"
    "gICAgAAAAABwiICAuIiIcAAAAACIiIj4iIiIiAAAAABwICAgICAgcAAAAAA4EBAQEJCQYAAAAACIkKDAwKCQiAAA"
    "AACAgICAgICA+AAAAACI2KioiIiIiAAAAACIiMiomIiIiAAAAABwiIiIiIiIcAAAAADwiIiI8ICAgAAAAABwiIiI"
    "iIiocAgAAADwiIiI8KCQiAAAAABwiIBwCAiIcAAAAAD4ICAgICAgIAAAAACIiIiIiIiIcAAAAACIiIhQUFAgIAAA"
    "AACIiIiIqKjYiAAAAACIiFAgIFCIiAAAAACIiFBQICAgIAAAAAD4CBAgQICA+AAAAABwQEBAQEBAcAAAAABAQCAg"
    "EBAICAAAAABwEBAQEBAQcAAAACBQiAAAAAAAAAAAAAAAAAAAAAAAAPgAQCAAAAAAAAAAAAAAAAAAAHAIeIiIeAAA"
    "AACAgPCIiIiI8AAAAAAAAHCIgICIcAAAAAAICHiIiIiIeAAAAAAAAHCI+ICAeAAAAAAYIHAgICAgIAAAAAAAAHiI"
    "iIiIeAhwAACAgPCIiIiIiAAAACAgAGAgICAgcAAAAAgIABgICAgICEgwAABAQEhQYGBQSAAAAABgICAgICAgcAAA"
    "AAAAAPCoqKioqAAAAAAAAPCIiIiIiAAAAAAAAHCIiIiIcAAAAAAAAPCIiIiI8ICAAAAAAHiIiIiIeAgIAAAAALjA"
    "gICAgAAAAAAAAHiAcAgI8AAAAAAgIHAgICAgGAAAAAAAAIiIiIiIeAAAAAAAAIiIUFAgIAAAAAAAAIiIqKiocAAA"
    "AAAAAIhQICBQiAAAAAAAAIiIiIiIeAhwAAAAAPgQIECA+AAAAAAYICBAICAgGAAAAAAgICAgICAgIAAAAABgEBAI"
    "EBAQYAAAAEiokAAAAAAAAAAA"
)
# --- END CARRIED hf_font ROWS ---

# --- BEGIN CARRIED hf_gif.mpy ---
# hf_gif.mpy, a MicroPython native module (5863 bytes), carried as base64 and checked against its SHA-256
# before it is written. How it was built: hf_gif.c is our own wrapper (MIT) around Larry Bank's AnimatedGIF
# decoder: gif.c and its two headers AnimatedGIF.h and AnimatedGIF_circuitpy.h, unmodified, exactly as
# CircuitPython 10.3.1 ships them (https://github.com/bitbank2/AnimatedGIF, Apache-2.0; CircuitPython's copy:
# https://github.com/adafruit/circuitpython/tree/c9dee12beed76e4ffa11d2d6d99ff104fc976c3a/lib/AnimatedGIF).
# Compiled for xtensawin (ESP32-S3), mpy format 6.3, MicroPython 1.29.0 ONLY, with MicroPython's natmod
# toolchain (py/dynruntime.mk, mpy_ld); it links MicroPython's dynruntime glue (MIT). The build files
# (hf_gif.c, Makefile, build.sh, BUILD.md) are in the HippaFone source repository.
_GIF_B64 = (
    "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"
)
_GIF_SHA256 = "f61f71e5894ee5a9691fa767c05114c793a39c97b75fa24c913fcd52ffa6e127"
# --- END CARRIED hf_gif.mpy ---

# --- BEGIN CARRIED licenses/OFL-1.1-Terminus.txt ---
# Licence text for /licenses/OFL-1.1-Terminus.txt. Upstream: https://raw.githubusercontent.com/adafruit/circuitpython/10.3.1/LICENSES/OFL-1.1.txt
# upstream SHA-256 797832eda5ff4360a10fee3be94a3250995e76423b79675c9c44204c37ca492d; edited: first line (the REUSE template's placeholder) replaced by the font's own copyright line; the template's "with Reserved Font Name <Reserved Font Name>. " removed (the font names none).
# Carried text: 4231 bytes, SHA-256 7b59d97d736829b923d256d013f55f5c95701c467340cd5e0764123d161b3333.
_PACKED["licenses/OFL-1.1-Terminus.txt"] = (
    "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"
    "F8VzJ/4N+waqKw=="
)
# --- END CARRIED licenses/OFL-1.1-Terminus.txt ---

# --- BEGIN CARRIED licenses/Apache-2.0-AnimatedGIF.txt ---
# Licence text for /licenses/Apache-2.0-AnimatedGIF.txt. Upstream: https://raw.githubusercontent.com/bitbank2/AnimatedGIF/c2478eca7aa2f3b7a09bdc583e5a4a43d03ac0d9/LICENSE
# upstream SHA-256 63fefff6dd199d109389e0f413579387e9ca9cfdeeae961ecdbcb120d08432e0.
# Carried text: 11419 bytes, SHA-256 63fefff6dd199d109389e0f413579387e9ca9cfdeeae961ecdbcb120d08432e0.
_PACKED["licenses/Apache-2.0-AnimatedGIF.txt"] = (
    "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"
)
# --- END CARRIED licenses/Apache-2.0-AnimatedGIF.txt ---

# --- BEGIN CARRIED licenses/MIT-MicroPython.txt ---
# Licence text for /licenses/MIT-MicroPython.txt. Upstream: https://raw.githubusercontent.com/micropython/micropython/v1.29.0/LICENSE
# upstream SHA-256 80d3459978572b5bbb1dd274a98b01a625aeff467588ad69cefdf7eb607c1306.
# Carried text: 3419 bytes, SHA-256 80d3459978572b5bbb1dd274a98b01a625aeff467588ad69cefdf7eb607c1306.
_PACKED["licenses/MIT-MicroPython.txt"] = (
    "eNqtVktzozgQvvMruubkzBo7cWbmsDdi44RaG1xAJpu9pGQQRhtAlCRiM79+u/EjdjLO1G5tKpWUWt1fvz8U5xzm"
    "XgwzkfBKc+jh4cKyxrJulVjlBnrJBYwur67t0eXoG0xYKXgFiwHccqlW3LIWXJVCayErEBpyrviyhZVileFpHzLF"
    "OcgMkpyhdh+MBFa1UHOl0UAuDROVqFbAIEGPFmqaHGG0zMyaKY7KKTCtZSIY4kEqk6bklWGG/GWi4Bp6BlP4FO0s"
    "Pl10TlLOCktUQHf7K1gLk8vGgOLaKJEQRh9ElRRNSjHsrwtRip0HMu/KoC0EbTRmQHH2oZSpyOg/79Kqm2UhdN6H"
    "VBD0sjEo1CTsqtqnPIZSgeZFYSGCwLi7XF+j63Qo9JoKanYl0iRZ57I8zURoK2tUhS55Z5NKLFnn8W+eGJKQeiaL"
    "Qq4ptURWqaCM9O+WFeMVW8oX3uWy7XIlDYa6DYEaUL92dXelc1YUsOS7gqFfUVkk2qejyL022HjBCqil6vy9TXOA"
    "/u9ciIJp/OCELngRLMLguzdxJ/DJifD8qQ8PXnwX3MeAGqHjx48QTMHxH+EPz5/0wf1zEbpRBEFoefPFzHNR5vnj"
    "2f3E82/hBu38AAfaw0lG0DgAcriD8tyIwOZuOL7Do3Pjzbz4sW9NvdgnzGkQggMLJ4y98f3MCWFxHy6CyEX3E4T1"
    "PX8aohd37vrxAL2iDNzveIDozpnNyJXl3GP0IcUH42DxGHq3dzHcBbOJi8IbFyNzbmbu1hUmNZ453rwPE2fu3Lqd"
    "VYAooUVq2+jg4c4lEflz8Hcce4FPaYwDPw7x2Mcsw/hg+uBFbh+c0IuoINMwmPctKidaBB0I2vnuFoVKDScdQRU6"
    "30fuARAmrjNDLGyPf9I+7Kb9P/9Y1n2Fa40cUPNEZAIHTeIAqbUgdtJIJ0uOU01rfpjj3Zp14/s606yuC5xM2lya"
    "0y1bdJyAA654LbUwUrWYg4fb8SLShu21Stbu5xxYul0dVhxh57JIcUEH2216YUrIRndD3038XCRKLlrkk+oEC12r"
    "1K6ZMu0rx5mcGdroXRYpNBViI5VkGbJpheuMy6gHgJ70IVcNZKqbskTfutvGriAGCdfqKoSsVHCGFoojzo4T8LjN"
    "kEqVCoVsIRWtb4b7i5RClT4up/WasqhQp+x4cQC+NLvAe7OL28XMPgSfyJSC1ETXXRz0WZBV0VoNXaeNIkKiUJeN"
    "KFKolUyo3RQQaiLbANVnzxuJLGsMOMVyNSrhHTxWfbj7UAH+DFMlXrAZ3aETJMn11eUl9G6iiX1tJwVD1zvdQixf"
    "9cbzyIuevkLPqVmSc3s0uLx4e/vtzC3T2ZdzVxtT6J95fw1QVplYncg6uU6UqI1+d3FkBD0qNzq0pbIL/Cqqi/c4"
    "YYM9HpTs+aB9FN6Sq2de8NZOl/bVZrMN9Mu7QIdLg2yeIERES7c9DGfe2PUj90gtUW1tpM2KFU6SyUvMHInyWANr"
    "nrepkit8OfS8aHx6VXKDq3WmWqhgTMEzfV5hLeqzl2Vb8bWxK1EuC36mW5XKNmcBqk39tB2vvcr4rYqUGTP7AK/e"
    "Q8iaVzYrzwdZi0TaOn0+q6D41dezl9qU1yMs41kFI6q20cujhenEzY/O6C/8eyRdix8VN1+fj9erkCsJvYY4J5jO"
    "7KvB1e6io7uTrRtdXp4Oen6+tdvoRYksVYjq+UO1KbJaGAfRYZy7xxocxHyT8JqY6SgVruvr0SlMXddPmpsn1ph8"
    "8PnMPKj6jVWJr7nNE98YxQbJx2tdyORZ/0p127JTS2xQ+plM5uOJHdFzHLcUPxLRw+Fl7qwwW3r8wvfR2yoS4JMw"
    "lBM95n+Dj0reIjeXT53N1uWvLJaSqVT/hK0MEnVT76E+pLzO4PNwp5p/WEYqBn/5j7VA41xq8++thz94nbfqTbFU"
    "8n5MhkbK4mjw06wZ1C1+CWk4r4mZ8XN3Yf0D+ivbBg=="
)
# --- END CARRIED licenses/MIT-MicroPython.txt ---

# --- BEGIN CARRIED licenses/MIT-adafruit_hx8357.txt ---
# Licence text for /licenses/MIT-adafruit_hx8357.txt. Upstream: https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_HX8357/2.0.4/LICENSE
# upstream SHA-256 b630470d62a9895275ef586367ece8100964eaa841042afe44136d634dfa7165.
# Carried text: 1115 bytes, SHA-256 b630470d62a9895275ef586367ece8100964eaa841042afe44136d634dfa7165.
_PACKED["licenses/MIT-adafruit_hx8357.txt"] = (
    "eNpdUktv2zAMvutXED21gNc9bttNsZVGmF+QnWY5KrYca3CswJIX9N+PdNJ2HWDAIEV+L6nuDWSyhtQ2ZvQG7rF4"
    "YCx255fJHvsA980DfPvy9TtkZrDea0jNatBj82lnh8Hqk4fOTcBb3U2zDSDHdvZhssYzVprphCvWjWA99GYyhxc4"
    "TnoMpo2gm4wB10HT6+loIggO9PgCZzN5XHCHoO1oxyNoaFAMw8nQI4x3XbjoyeBwC9p711iNeNC6Zj6ZMehAfJ0d"
    "jIf7gO7uqtvG3cNC0ho9MDsCnb0ewcWG3s0BJkPiG8KIwI7NMLek4fV4sCd7Y6D1JSHPEHT26IB0RnByre3obxZb"
    "5/mAufURtJagD3PApqfmEnhEPj5jgt4MA0META4Wr+/qlhmSfqZAwy0iT51L704fnVjPunkakdIsO63DyBbG36YJ"
    "1KHxzg2Du5C1xo2tJUf+B2M1HumD+2MWL9cHMLqAUq8S6ALO77d6O/K9HgY4mFtgyIvx6n/sTETvA1681QOc3bTw"
    "/W/zEfk3AqpiXe+4EiArKFXxLBORwB2vsL6LYCfrTbGtAScUz+s9FGvg+R5+yjyJQPwqlagqKBSTWZlKgT2Zx+k2"
    "kfkTrHAvL/CtS3zkCFoXQIQ3KCkqAsuEijdY8pVMZb2P2FrWOWGuCwUcSq5qGW9TrqDcqrKoBNInCJvLfK2QRWQi"
    "rx+RFXsgnrGAasPTlKgY36J6RfogLsq9kk+bGjZFmghsrgQq46tUXKnQVJxymUWQ8Iw/iWWrQBTFaOyqDnYbQS3i"
    "4/jFtSxyshEXea2wjNClqt9Wd7ISEXAlKwpkrYosYhQnbhQLCO7l4opCUcOHG8ERqreVeAOERPAUsSpaJouvw4/s"
    "L2GmZHM="
)
# --- END CARRIED licenses/MIT-adafruit_hx8357.txt ---

# --- BEGIN CARRIED licenses/MIT-st7789py.txt ---
# Licence text for /licenses/MIT-st7789py.txt. Upstream: https://raw.githubusercontent.com/russhughes/st7789py_mpy/7265925bd0c092e8105200d18b2dba9dfbc12c27/LICENSE
# upstream SHA-256 753fb979c31b6bc93ef513f705af993ae72857c5ea2d4b79ff6cc983c2d2de81.
# Carried text: 1111 bytes, SHA-256 753fb979c31b6bc93ef513f705af993ae72857c5ea2d4b79ff6cc983c2d2de81.
_PACKED["licenses/MIT-st7789py.txt"] = (
    "eNplUltv2jAUfvevOOpTK2Vd1z1tbyYxjbXc5IQyHkNiiNcQo9gZ4t/vnEDbdZMQ6Fy+2zGprCAxjR6cZiy0x/No"
    "9p2H2+YOHh8eHz7h11dQk3MQT/tOu/92vnwD+bseYKF7+2K35969mDNjhR4PxjljBzAOOj3q7Rn2Yz143QawG7UG"
    "u4Omq8e9DsBbqIczHPXoEGC3vjaDGfZQQ4NyDDd9hzTO7vypHjUut1A7ZxtTIx+0tpkOevC1J72d6bWDW99puCmv"
    "iJu7WaTVdc/MADR7HcHJ+M5OHkbt/Gga4gjADE0/teThddybg7kqEHy+gWNIOjlMQD4DONjW7OhXz7GO07Y3rgug"
    "NUS9nTw2HTXngweU47Mdwem+Z8hg0Pec9d3dvEPWj3RQfz2Ro86ps4ePSYxju2kcUFLPmNbiyWbFX7rx1KH1ne17"
    "e6JojR1aQ4ncd8YqHNVb+1vPWS5PPFiPVi8W6AGO7696Hbmu7nvY6uvBUBfPW/8VZyR55/HhTd3D0Y6z3r8x71E/"
    "FlDmy2rNlQBZQqHyZxmJCG54ifVNAGtZxfmqAtxQPKs2kC+BZxv4IbMoAPGzUKIsIVdMpkUiBfZkFiarSGZPsEBc"
    "luN/XaayQtIqBxK8UklRElkqVBhjyRcykdUmYEtZZcS5zBVwKLiqZLhKuIJipYq8FCgfIW0ms6VCFZGKrLpHVeyB"
    "eMYCypgnCUkxvkL3ivxBmBcbJZ/iCuI8iQQ2FwKd8UUiLlIYKky4TAOIeMqfxIzKkUUxWru4g3UsqEV6HD9hJfOM"
    "YoR5ViksA0ypqjfoWpYiAK5kSQdZqjwNGJ0TEflMgrhMXFjo1PDhRXCF6lUp3gghEjxBrpLAFPF1+Z79AekcYbk="
)
# --- END CARRIED licenses/MIT-st7789py.txt ---

# --- BEGIN CARRIED licenses/micropython-lib-LICENSE.txt ---
# Licence text for /licenses/micropython-lib-LICENSE.txt. Upstream: https://raw.githubusercontent.com/micropython/micropython-lib/446038da9b03ad2aa67e256134937e19ff8d0a73/LICENSE
# upstream SHA-256 a38cf48836aa313254cdcf3de9fb7c24da4a2eab75ead2cc0cecd998336e7800.
# Carried text: 14363 bytes, SHA-256 a38cf48836aa313254cdcf3de9fb7c24da4a2eab75ead2cc0cecd998336e7800.
_PACKED["licenses/micropython-lib-LICENSE.txt"] = (
    "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"
)
# --- END CARRIED licenses/micropython-lib-LICENSE.txt ---

# --- BEGIN CARRIED licenses/MIT-TinyUF2.txt ---
# Licence text for /licenses/MIT-TinyUF2.txt. Upstream: https://raw.githubusercontent.com/adafruit/tinyuf2/0.36.0/LICENSE
# upstream SHA-256 c5bfb6825385bbba9b115194c61f80f0c7c1acd170282a63f9a3af2fef80b396.
# Carried text: 1065 bytes, SHA-256 c5bfb6825385bbba9b115194c61f80f0c7c1acd170282a63f9a3af2fef80b396.
_PACKED["licenses/MIT-TinyUF2.txt"] = (
    "eNpdUktv2zAMvutXEDm1gNEVPe6mxEotzC/IyrIcFVuJNThWYCkL+u9HOmm7DghgiOT3IlNIDblr7RgsYyt/fpvc"
    "sY/w0D7Cy/PLM2QGdG/anrHaTicXgvMjuAC9nez+DY6TGaPtEjhM1oI/QNub6WgTiB7M+AZnOwUE+H00bnTjEQy0"
    "KMJwMvZIE/whXs1kcbgDE4JvnUE+6Hx7Odkxmkh6BzfYAA+xt7Bo7ojF4yzSWTMwNwL13ltwdbH3lwiTDXFyLXEk"
    "4MZ2uHTk4b09uJO7KxB8Th4Ykl4CJiCfCZx85w70tXOs82U/uNAn0Dmi3l8iFgMV5xUmlOObnyDYYWDI4ND3nPXT"
    "3TxD1s+00HhfUaDKtfenr0lcYIfLNKKknTGdx5XNir9tG6lC4wc/DP5K0Vo/do4She+MaWyZvf9j5yy3w44+otWb"
    "BTrA+fOq91bozTDA3t4Xhrq4XvNPnInkQ8TDOzPA2U+z3v8xn1A/E9BUa73lSoBsoFbVT5mKFBa8wfciga3UWbXR"
    "gBOKl3oH1Rp4uYMfskwTEL9qJZoGKsVkUedSYE2Wq3yTyvIVlogrK/z3ykJqJNUVkOCdSoqGyAqhVhk++VLmUu8S"
    "tpa6JM51pYBDzZWWq03OFdQbVVeNQPkUaUtZrhWqiEKU+glVsQbiJz6gyXiekxTjG3SvyB+sqnqn5GumIavyVGBx"
    "KdAZX+biJoWhVjmXRQIpL/irmFEVsihGYzd3sM0ElUiP42+lZVVSjFVVaoXPBFMq/QHdykYkwJVsaCFrVRUJo3Ui"
    "oppJEFeKGwutGr5cBEfovWnEByGkgufI1RCYIr4PP7G/vYBSkQ=="
)
# --- END CARRIED licenses/MIT-TinyUF2.txt ---


class Problem(Exception):
    """Something the person running the script has to fix; the message says what."""


# ---------------------------------------------------------------- USB serial ports, without pyserial

@dataclass
class Port:
    device: str
    vid: int | None = None
    pid: int | None = None
    description: str = ""

    def ids(self):
        return (self.vid, self.pid)

    def label(self):
        usb = "USB %04X:%04X" % (self.vid, self.pid) if self.vid is not None else "USB ids unknown"
        what = ("MicroPython on an ESP32-S3" if self.ids() == MICROPYTHON_ID else
                "ESP32-S3 in ROM download mode" if self.ids() == ROM_ID else self.description)
        return "%-14s %s  %s" % (self.device, usb, what)


def _port_key(name):
    m = re.match(r"(\D*)(\d+)$", os.path.basename(name))
    return (m.group(1), int(m.group(2))) if m else (name, 0)


def _subkeys(winreg, key):
    i = 0
    while True:
        try:
            yield winreg.EnumKey(key, i)
        except OSError:
            return
        i += 1


def _list_windows():
    import ctypes
    import winreg
    names = set()
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as k:
            i = 0
            while True:
                try:
                    names.add(str(winreg.EnumValue(k, i)[1]).upper())
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    cfg = ctypes.WinDLL("cfgmgr32")
    found = {}
    try:
        usb = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Enum\USB")
    except OSError:
        usb = None
    if usb:
        with usb:
            for dev in _subkeys(winreg, usb):
                m = re.match(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", dev, re.I)
                if not m:
                    continue
                with winreg.OpenKey(usb, dev) as dk:
                    for inst in _subkeys(winreg, dk):
                        try:
                            with winreg.OpenKey(dk, inst + r"\Device Parameters") as pk:
                                name = str(winreg.QueryValueEx(pk, "PortName")[0]).upper()
                        except OSError:
                            continue
                        # the registry remembers unplugged devices too: is this one here now?
                        node = ctypes.c_ulong()
                        if name not in names or cfg.CM_Locate_DevNodeW(
                                ctypes.byref(node), "USB\\%s\\%s" % (dev, inst), 0) != 0:
                            continue
                        desc = ""
                        try:
                            with winreg.OpenKey(dk, inst) as ik:
                                desc = str(winreg.QueryValueEx(ik, "FriendlyName")[0])
                        except OSError:
                            pass
                        found[name] = Port(name, int(m.group(1), 16), int(m.group(2), 16), desc)
    for name in names:
        found.setdefault(name, Port(name))
    return sorted(found.values(), key=lambda p: _port_key(p.device))


def _list_posix():
    ports = []
    for tty in glob.glob("/sys/class/tty/ttyACM*") + glob.glob("/sys/class/tty/ttyUSB*"):
        usb = os.path.realpath(os.path.join(tty, "device"))
        for _ in range(4):                       # from the interface folder up to the USB device
            if os.path.exists(os.path.join(usb, "idVendor")):
                break
            usb = os.path.dirname(usb)

        def attr(name):
            try:
                with open(os.path.join(usb, name)) as f:
                    return f.read().strip()
            except OSError:
                return ""
        vid, pid = attr("idVendor"), attr("idProduct")
        ports.append(Port("/dev/" + os.path.basename(tty), int(vid, 16) if vid else None,
                          int(pid, 16) if pid else None, attr("product")))
    if not ports:                                # macOS, or no sysfs
        ports = [Port(d) for d in glob.glob("/dev/cu.usbmodem*")]
    return sorted(ports, key=lambda p: _port_key(p.device))


def list_ports():
    return _list_windows() if os.name == "nt" else _list_posix()


class WinSerial:
    """A COM port through the Win32 API (ctypes), opened as pyserial does: 115200 8N1, DTR and RTS on."""

    def __init__(self, name):
        import ctypes
        from ctypes import wintypes
        self.ct, self.wt = ctypes, wintypes
        k = self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateFileW.restype = wintypes.HANDLE
        k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        for f in (k.ReadFile, k.WriteFile):
            f.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        for f in (k.GetCommState, k.SetCommState, k.SetCommTimeouts):
            f.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.PurgeComm.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.SetupComm.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
        k.ClearCommError.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]

        class COMSTAT(ctypes.Structure):
            _fields_ = [("flags", wintypes.DWORD), ("cbInQue", wintypes.DWORD), ("cbOutQue", wintypes.DWORD)]
        self.comstat, self.errors = COMSTAT(), wintypes.DWORD()
        self.h = None
        h = k.CreateFileW("\\\\.\\" + name, 0xC0000000, 0, None, 3, 0, None)   # read+write, existing
        if h is None or h == wintypes.HANDLE(-1).value:
            err = ctypes.get_last_error()
            if err == 5:
                raise Problem("%s is in use by another program. Close it (a BIPES tab, Thonny, "
                              "mpremote, a serial terminal) and try again." % name)
            if err == 2:
                raise Problem("%s is gone (unplugged, or the board restarted)." % name)
            raise Problem("cannot open %s (Windows error %d)" % (name, err))
        self.h = h

        class DCB(ctypes.Structure):
            _fields_ = [("DCBlength", wintypes.DWORD), ("BaudRate", wintypes.DWORD),
                        ("fFlags", wintypes.DWORD), ("wReserved", wintypes.WORD),
                        ("XonLim", wintypes.WORD), ("XoffLim", wintypes.WORD),
                        ("ByteSize", ctypes.c_ubyte), ("Parity", ctypes.c_ubyte),
                        ("StopBits", ctypes.c_ubyte), ("XonChar", ctypes.c_char),
                        ("XoffChar", ctypes.c_char), ("ErrorChar", ctypes.c_char),
                        ("EofChar", ctypes.c_char), ("EvtChar", ctypes.c_char),
                        ("wReserved1", wintypes.WORD)]

        class TIMEOUTS(ctypes.Structure):
            _fields_ = [(n, wintypes.DWORD) for n in (
                "ReadIntervalTimeout", "ReadTotalTimeoutMultiplier", "ReadTotalTimeoutConstant",
                "WriteTotalTimeoutMultiplier", "WriteTotalTimeoutConstant")]

        k.SetupComm(h, 65536, 65536)
        dcb = DCB()
        dcb.DCBlength = ctypes.sizeof(DCB)
        k.GetCommState(h, ctypes.byref(dcb))
        dcb.BaudRate, dcb.ByteSize, dcb.Parity, dcb.StopBits = 115200, 8, 0, 0
        # binary, DTR and RTS both on at once (on the ROM port, RTS on with DTR off would reset the chip)
        dcb.fFlags = 1 | (1 << 4) | (1 << 12)
        if not k.SetCommState(h, ctypes.byref(dcb)):
            err = ctypes.get_last_error()
            self.close()
            raise Problem("cannot set up %s (Windows error %d)" % (name, err))
        # a read returns at once with whatever is waiting, else waits up to 20 ms for a first byte
        k.SetCommTimeouts(h, ctypes.byref(TIMEOUTS(0xFFFFFFFF, 0xFFFFFFFF, 20, 0, 10000)))
        k.PurgeComm(h, 0x0C)                          # drop anything already buffered
        self.rbuf = ctypes.create_string_buffer(65536)

    def read(self, timeout):
        """Bytes that arrive within timeout seconds; returns as soon as there are any."""
        n = self.wt.DWORD()
        deadline = time.monotonic() + timeout
        while True:
            if not self.k.ReadFile(self.h, self.rbuf, len(self.rbuf), self.ct.byref(n), None):
                raise Problem("the board's port stopped working (unplugged?)")
            if n.value:
                return self.rbuf.raw[:n.value]
            if time.monotonic() >= deadline:
                return b""

    def poll(self):
        """Bytes already waiting, without waiting for more."""
        if not self.k.ClearCommError(self.h, self.ct.byref(self.errors), self.ct.byref(self.comstat)):
            raise Problem("the board's port stopped working (unplugged?)")
        return self.read(0) if self.comstat.cbInQue else b""

    def write(self, data):
        n = self.wt.DWORD()
        mv = memoryview(bytes(data))
        while mv:
            chunk = bytes(mv[:16384])
            if not self.k.WriteFile(self.h, chunk, len(chunk), self.ct.byref(n), None) or not n.value:
                raise Problem("writing to the board failed (unplugged?)")
            mv = mv[n.value:]

    def close(self):
        if self.h:
            self.k.CloseHandle(self.h)
            self.h = None


class PosixSerial:
    """A tty in raw mode through termios: 115200 8N1, DTR and RTS on."""

    def __init__(self, name):
        import fcntl
        import termios
        self.fd = None
        try:
            self.fd = os.open(name, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        except PermissionError:
            raise Problem("no permission to open %s. Add yourself to the dialout group:\n"
                          "    sudo usermod -aG dialout $USER\nthen log out and back in." % name)
        except FileNotFoundError:
            raise Problem("%s is gone (unplugged, or the board restarted)." % name)
        except OSError as e:
            raise Problem("cannot open %s: %s" % (name, e))
        try:
            fcntl.ioctl(self.fd, termios.TIOCEXCL)     # keep other programs (ModemManager) out
        except (OSError, AttributeError):
            pass
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = attrs[1] = attrs[3] = 0             # iflag, oflag, lflag: raw
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[4] = attrs[5] = termios.B115200
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        try:
            fcntl.ioctl(self.fd, termios.TIOCMBIS, struct.pack("I", termios.TIOCM_DTR | termios.TIOCM_RTS))
        except (OSError, AttributeError):
            pass
        termios.tcflush(self.fd, termios.TCIOFLUSH)

    def read(self, timeout):
        import select
        r, _, _ = select.select([self.fd], [], [], max(timeout, 0))
        if not r:
            return b""
        try:
            data = os.read(self.fd, 65536)
        except BlockingIOError:
            return b""
        except OSError:
            raise Problem("the board's port stopped working (unplugged?)")
        if not data:
            raise Problem("the board's port closed (unplugged?)")
        return data

    def poll(self):
        return self.read(0)

    def write(self, data):
        import select
        mv = memoryview(bytes(data))
        while mv:
            select.select([], [self.fd], [], 5)
            try:
                n = os.write(self.fd, mv)
            except BlockingIOError:
                continue
            except OSError:
                raise Problem("writing to the board failed (unplugged?)")
            mv = mv[n:]

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def open_port(name):
    return WinSerial(name) if os.name == "nt" else PosixSerial(name)


# ---------------------------------------------------------------- the TinyUF2 drive

def uf2_drives():
    """[(folder, INFO_UF2.TXT text)] for every UF2 bootloader drive that is open (mounted)."""
    found = []
    for r in _drive_roots():
        try:
            with open(os.path.join(r, "INFO_UF2.TXT"), encoding="ascii", errors="replace") as f:
                found.append((r, f.read()))
        except OSError:
            pass
    return found


def is_our_tinyuf2(info):
    """True for TinyUF2 on a Feather ESP32-S3 (5477)."""
    return "TinyUF2" in info and ("ESP32-S3" in info or "ESP32S3" in info) and "Feather" in info


def tinyuf2_version(info):
    m = re.search(r"TinyUF2 Bootloader (\d+)\.(\d+)\.(\d+)", info)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


# ---------------------------------------------------------------- MicroPython's raw REPL

class BoardError(Problem):
    pass


class Board:
    """MicroPython's raw REPL (the protocol mpremote uses)."""

    BANNER = b"raw REPL; CTRL-B to exit\r\n"

    def __init__(self, port):
        self.port = port
        self.buf = b""
        # The S3's own USB has flow control, so a whole command can go at once: six times faster
        # than raw paste (its window on this board is 128 bytes). The helper's hash is checked
        # on the board, and board_write falls back to raw paste if it ever arrives damaged.
        self.fast = True
        self.raw_paste = True

    def _fill(self, timeout):
        data = self.port.read(timeout)
        self.buf += data
        return data

    def _poll(self):
        data = self.port.poll()
        self.buf += data
        return data

    def read_until(self, marker, timeout):
        deadline = time.monotonic() + timeout
        while marker not in self.buf:
            left = deadline - time.monotonic()
            if left <= 0:
                raise BoardError("the board stopped answering (waited for %r; last bytes %r)"
                                 % (marker, self.buf[-60:]))
            self._fill(min(left, 0.2))
        i = self.buf.index(marker) + len(marker)
        out, self.buf = self.buf[:i], self.buf[i:]
        return out

    def read_exact(self, n, timeout):
        deadline = time.monotonic() + timeout
        while len(self.buf) < n:
            left = deadline - time.monotonic()
            if left <= 0:
                raise BoardError("the board stopped answering")
            self._fill(min(left, 0.2))
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def drain(self, quiet=0.3, limit=3.0):
        end = time.monotonic() + limit
        while time.monotonic() < end and self._fill(quiet):
            pass
        self.buf = b""

    def enter(self):
        """Stop the running program and enter the raw REPL with a fresh interpreter."""
        for attempt in range(3):
            self.port.write(b"\r\x03")
            time.sleep(0.1)
            self.port.write(b"\x03")
            self.drain()
            self.port.write(b"\r\x01")
            try:
                self.read_until(self.BANNER + b">", 3)
                break
            except BoardError:
                if attempt == 2:
                    raise BoardError("the board does not answer like MicroPython")
        self.port.write(b"\x04")
        self.read_until(b"soft reboot\r\n", 10)
        self.read_until(self.BANNER, 10)

    def exec(self, code, timeout=30):
        """Run code on the board. Returns what it printed; raises BoardError with its traceback."""
        data = code.encode() if isinstance(code, str) else code
        self.read_until(b">", timeout)
        if self.fast:
            self.port.write(data + b"\x04")
            if self.read_exact(2, timeout) != b"OK":
                raise BoardError("the board did not take a command")
            return self._result(timeout)
        if self.raw_paste:
            self.port.write(b"\x05A\x01")
            head = self.read_exact(2, 5)
            if head == b"R\x01":
                self._paste(data)
                return self._result(timeout)
            if head != b"R\x00":                   # firmware from before raw paste: banner again
                self.read_until(self.BANNER + b">", 5)
            self.raw_paste = False
        for i in range(0, len(data), 256):
            self.port.write(data[i:i + 256])
            time.sleep(0.01)
        self.port.write(b"\x04")
        if self.read_exact(2, 5) != b"OK":
            raise BoardError("the board did not take a command")
        return self._result(timeout)

    def _paste(self, data):
        window = struct.unpack("<H", self.read_exact(2, 5))[0]
        remain = window
        i = 0
        while i < len(data):
            while remain == 0 or self.buf or self._poll():
                if not self.buf:
                    if not self._fill(10):
                        raise BoardError("the board stopped answering during a paste")
                    continue
                c, self.buf = self.buf[:1], self.buf[1:]
                if c == b"\x01":                   # room for another window of bytes
                    remain += window
                elif c == b"\x04":                 # the board ended the paste early
                    self.port.write(b"\x04")
                    return
                else:
                    raise BoardError("unexpected byte %r from the board during a paste" % c)
            part = data[i:i + remain]
            self.port.write(part)
            remain -= len(part)
            i += len(part)
        self.port.write(b"\x04")
        self.read_until(b"\x04", 10)

    def _result(self, timeout):
        out = self.read_until(b"\x04", timeout)[:-1]
        err = self.read_until(b"\x04", timeout)[:-1]
        if err:
            raise BoardError("the board reported an error:\n" + err.decode("utf-8", "replace"))
        return out.decode("utf-8", "replace")

    def eval(self, code, timeout=30):
        """Run code whose last printed line is a repr(); returns that value."""
        out = self.exec(code, timeout).strip().splitlines()
        try:
            return ast.literal_eval(out[-1])
        except (IndexError, ValueError, SyntaxError):
            raise BoardError("unexpected answer from the board: %r" % out)

    def leave(self):
        """Back to the normal prompt, then Ctrl-D: the board restarts its own main.py, if any."""
        self.read_until(b">", 5)
        self.port.write(b"\r\x02")
        self.read_until(b">>> ", 5)
        self.port.write(b"\x04")


BOARD_INFO = """\
import sys, os, gc
u = os.uname()
try:
    s = os.statvfs('/')
    free = s[0] * s[3]
except Exception:
    free = -1
print(repr((sys.implementation.name, getattr(sys.implementation, '_machine', u.machine), u.release, free)))
"""

BOARD_HASHES = """\
import hashlib, binascii
def _hf_hash(p):
    try:
        f = open(p, 'rb')
    except OSError:
        return None
    h = hashlib.sha256()
    while True:
        d = f.read(4096)
        if not d:
            break
        h.update(d)
    f.close()
    return binascii.hexlify(h.digest()).decode()
print(repr([_hf_hash(p) for p in %r]))
"""


def board_hashes(board, names):
    return dict(zip(names, board.eval(BOARD_HASHES % list(names)))) if names else {}


def board_write(board, name, data):
    """Write data to name on the board through name.tmp, check its SHA-256 there, then rename.
    If it fails while commands go at full speed, start again carefully (raw paste)."""
    try:
        _board_write(board, name, data)
    except BoardError:
        if not board.fast:
            raise
        board.fast = False
        board.enter()
        _board_write(board, name, data)


def _board_write(board, name, data):
    tmp = name + ".tmp"
    board.exec("import binascii, os\n_hf_f = open(%r, 'wb')" % tmp)
    for i in range(0, len(data), CHUNK):
        board.exec("_hf_f.write(binascii.a2b_base64(%r))" % base64.b64encode(data[i:i + CHUNK]).decode())
    board.exec("_hf_f.close()")
    want = hashlib.sha256(data).hexdigest()
    got = board_hashes(board, [tmp])[tmp]
    if got != want:
        board.exec("os.remove(%r)" % tmp)
        raise BoardError("%s did not arrive intact on the board" % name)
    board.exec("try:\n    os.remove(%r)\nexcept OSError:\n    pass\nos.rename(%r, %r)" % (name, tmp, name))


def board_text(board, name):
    """A text file from the board, or None if it is not there."""
    return board.eval("try:\n    _hf_f = open(%r)\n    print(repr(_hf_f.read()))\n    _hf_f.close()\n"
                      "except OSError:\n    print('None')" % name)


# ---------------------------------------------------------------- the ESP32-S3 ROM loader

class Rom:
    """The ESP32-S3's built-in loader (ROM download mode), spoken directly: SLIP frames and the
    commands esptool uses, enough to write flash, check it by MD5 and restart the chip."""

    BLOCK = 0x400                                  # the ROM loader's flash write block

    def __init__(self, port):
        self.port = port
        self.buf = b""
        self.status_len = 4

    def _send(self, op, data=b"", chk=0):
        pkt = struct.pack("<BBHI", 0, op, len(data), chk) + data
        self.port.write(b"\xc0" + pkt.replace(b"\xdb", b"\xdb\xdd").replace(b"\xc0", b"\xdb\xdc") + b"\xc0")

    def _frame(self, timeout):
        """The next SLIP frame, or None after timeout seconds."""
        deadline = time.monotonic() + timeout
        while True:
            start = self.buf.find(b"\xc0")
            if start >= 0:
                end = self.buf.find(b"\xc0", start + 1)
                if end > start + 1:
                    raw, self.buf = self.buf[start + 1:end], self.buf[end + 1:]
                    return raw.replace(b"\xdb\xdc", b"\xc0").replace(b"\xdb\xdd", b"\xdb")
                if end == start + 1:                # two ends in a row: the second starts a frame
                    self.buf = self.buf[end:]
                    continue
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            self.buf += self.port.read(min(left, 0.1))

    def command(self, op, data=b"", chk=0, timeout=3.0):
        """Send one command; returns (value, data) of its answer or raises Problem."""
        self._send(op, data, chk)
        deadline = time.monotonic() + timeout
        while True:
            raw = self._frame(max(deadline - time.monotonic(), 0))
            if raw is None:
                raise Problem("the ESP32-S3's loader did not answer (command 0x%02X)" % op)
            if len(raw) < 8 or raw[0] != 1 or raw[1] != op:
                continue                            # a late answer to something earlier
            value = struct.unpack_from("<I", raw, 4)[0]
            body = raw[8:]
            status = body[-self.status_len:]
            if len(status) < 2 or status[0] != 0:
                raise Problem("the ESP32-S3's loader refused command 0x%02X (error 0x%02X)"
                              % (op, status[1] if len(status) > 1 else 0xFF))
            return value, body[:-self.status_len]

    def sync(self):
        for _ in range(20):
            self.buf = b""
            self._send(0x08, b"\x07\x07\x12\x20" + b"\x55" * 32)
            end = time.monotonic() + 0.5
            while time.monotonic() < end:
                raw = self._frame(end - time.monotonic())
                if raw and len(raw) >= 10 and raw[0] == 1 and raw[1] == 0x08:
                    self.status_len = len(raw) - 8  # SYNC's answer is only the status
                    time.sleep(0.2)                 # it answers several times: drop the rest
                    self.port.poll()
                    self.buf = b""
                    return
        raise Problem("the ESP32-S3 in download mode did not answer. Press RESET and put it in "
                      "download mode again.")

    def chip_id(self):
        try:
            _, d = self.command(0x14)               # GET_SECURITY_INFO
            return struct.unpack_from("<I", d, 12)[0] if len(d) >= 16 else None
        except Problem:
            return None

    def prepare(self):
        self.command(0x0D, struct.pack("<II", 0, 0))                    # SPI_ATTACH
        self.command(0x0B, struct.pack("<IIIIII", 0, 4 << 20, 64 << 10, 4 << 10, 256, 0xFFFF))  # 4 MB

    def md5(self, offset, size):
        _, d = self.command(0x13, struct.pack("<IIII", offset, size, 0, 0),
                            timeout=max(5.0, 8.0 * size / (1 << 20)))
        return d.decode() if len(d) == 32 else d.hex()

    def write(self, offset, data, label, log):
        """Erase and write data at offset in 1 KB blocks, then check it with the chip's MD5."""
        data = data + b"\xff" * (-len(data) % 4)
        blocks = (len(data) + self.BLOCK - 1) // self.BLOCK
        log("  writing %s: %d KB at 0x%06X (erasing first) ..." % (label, len(data) // 1024, offset))
        self.command(0x02, struct.pack("<IIIII", len(data), blocks, self.BLOCK, offset, 0),
                     timeout=max(10.0, 30.0 * len(data) / (1 << 20)))      # FLASH_BEGIN erases
        padded = data + b"\xff" * (blocks * self.BLOCK - len(data))
        shown = -1
        for seq in range(blocks):
            block = padded[seq * self.BLOCK:(seq + 1) * self.BLOCK]
            chk = 0xEF
            for b in block:
                chk ^= b
            for attempt in range(3):
                try:
                    self.command(0x03, struct.pack("<IIII", len(block), seq, 0, 0) + block, chk, 5.0)
                    break
                except Problem:
                    if attempt == 2:
                        raise
            pct = (seq + 1) * 100 // blocks
            if pct // 10 != shown:
                shown = pct // 10
                sys.stdout.write("\r    %3d%%" % pct)
                sys.stdout.flush()
        sys.stdout.write("\n")
        if self.md5(offset, len(data)) != hashlib.md5(data).hexdigest():
            raise Problem("%s did not check out after writing (MD5). Run the script again." % label)

    def same(self, offset, data):
        data = data + b"\xff" * (-len(data) % 4)
        return self.md5(offset, len(data)) == hashlib.md5(data).hexdigest()

    def restart(self):
        """Clear the stay-in-download-mode flag and restart the chip with its RTC watchdog, as
        esptool's --after watchdog-reset does (a plain reset does not leave download mode)."""
        try:
            self.command(0x09, struct.pack("<IIII", 0x6000812C, 0, 1, 0))   # RTC_CNTL_OPTION1: force download off
        except Problem:
            pass
        regs = ((0x600080B0, 0x50D83AA1),                                    # WDT write protect: unlock
                (0x6000809C, 5000),                                         # WDT timeout
                (0x60008098, (1 << 31) | (5 << 28) | (1 << 8) | 2),         # WDT on: reset the system
                (0x600080B0, 0))                                            # lock again
        for addr, value in regs:
            try:
                self.command(0x09, struct.pack("<IIII", addr, value, 0xFFFFFFFF, 0), timeout=1.0)
            except Problem:
                break                                                       # it already restarted


# ---------------------------------------------------------------- firmware files

def cache_dir():
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "HippaFone"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "hippafone"
    return base / "cache"


def from_cache(sha):
    """The cached file named by its SHA-256 if it is there and intact, else None."""
    try:
        data = (cache_dir() / sha).read_bytes()
    except OSError:
        return None
    return data if hashlib.sha256(data).hexdigest() == sha else None


def download(name, log):
    """One of DOWNLOADS from its own home on the internet (urllib, like curl), kept in the cache
    afterwards; always checked against its fixed SHA-256."""
    url, sha = DOWNLOADS[name]
    data = from_cache(sha)
    if data is not None:
        return data
    log("  downloading %s" % url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            break
        except (urllib.error.URLError, OSError) as e:
            if attempt == 2:
                raise Problem("cannot download %s: %s. Is the computer online?" % (url, getattr(e, "reason", e)))
            time.sleep(2)
    if hashlib.sha256(data).hexdigest() != sha:
        raise Problem("%s did not download intact (wrong SHA-256). Try again." % url)
    try:
        cache_dir().mkdir(parents=True, exist_ok=True)
        (cache_dir() / sha).write_bytes(data)
    except OSError:
        pass
    return data


def tinyuf2_parts(log):
    z = zipfile.ZipFile(io.BytesIO(download("tinyuf2.zip", log)))
    return [(offset, name, z.read(name)) for offset, name in TINYUF2_PARTS]



# ---------------------------------------------------------------- the libraries (carried above)

def carried(name):
    """The bytes of a carried text file (a _PACKED block)."""
    return zlib.decompress(base64.b64decode(_PACKED[name]))


# hf_font.py is written from its bitmap table: 95 glyphs of 12 bytes, ASCII 32 to 126.
FONT_WIDTH, FONT_HEIGHT, FONT_FIRST, FONT_COUNT = 6, 12, 32, 95
FONT_HEAD = '''# SPDX-License-Identifier: OFL-1.1
# Terminus Font 6x12 (ter-u12n.bdf), Copyright (C) 2018 Dimitar Toshkov Zhekov,
# SIL Open Font License 1.1. Source: https://raw.githubusercontent.com/adafruit/circuitpython/10.3.1/tools/fonts/ter-u12n.bdf
# The bitmap table below is converted from that BDF by HippaFone's scripts/bdf_to_mpy_font.py.
# Licence text on the board: /licenses/OFL-1.1-Terminus.txt
"""6x12 bitmap font, ASCII 32 to 126 (generated by scripts/bdf_to_mpy_font.py from ter-u12n.bdf).

ROWS holds 95 glyphs of 12 bytes (top row first); the 6 pixel columns are the top 6 bits of
each byte, bit 7 leftmost.
"""
WIDTH, HEIGHT, FIRST, COUNT = %d, %d, %d, %d
ROWS = (
'''


def make_font():
    """hf_font.py, the bytes to write to the Feather."""
    rows = base64.b64decode(_FONT_ROWS_B64)
    if len(rows) != FONT_COUNT * FONT_HEIGHT:
        raise Problem("the carried font table has the wrong size")
    out = [FONT_HEAD % (FONT_WIDTH, FONT_HEIGHT, FONT_FIRST, FONT_COUNT)]
    for i in range(FONT_COUNT):
        code = FONT_FIRST + i
        glyph = "".join("\\x%02x" % b for b in rows[i * FONT_HEIGHT:(i + 1) * FONT_HEIGHT])
        out.append('    b"%s"  # %d %s\n' % (glyph, code, "space" if code == 32 else chr(code)))
    out.append(")\n")
    return "".join(out).encode("ascii")


def gif_module():
    """hf_gif.mpy, checked against its SHA-256 before anything is written."""
    data = base64.b64decode(_GIF_B64)
    if hashlib.sha256(data).hexdigest() != _GIF_SHA256:
        raise Problem("the carried hf_gif.mpy does not match its SHA-256; this script file is damaged")
    return data


def make_helper(turn=None):
    """hippa.py with SCREEN_TURN set (as carried when turn is None)."""
    text = carried(HELPER).decode("utf-8")
    if turn is not None:
        text = re.sub(r"^SCREEN_TURN = \d+", "SCREEN_TURN = %d" % turn, text, count=1, flags=re.M)
    return text


def library_files():
    """{board name: bytes} of every library this script carries (sdcard.py is downloaded)."""
    files = {}
    for name in LIBRARIES:
        if name == "hf_font.py":
            files[name] = make_font()
        elif name == "hf_gif.mpy":
            files[name] = gif_module()
        else:
            files[name] = carried(name)
    return files


def licence_files():
    """{name: bytes} of the licence texts for /licenses, README.txt (the index) among them."""
    files = {name[len(LICENSE_DIR) + 1:]: carried(name) for name in _PACKED if name.startswith(LICENSE_DIR + "/")}
    files["MIT-HippaFone.txt"] = MIT_HIPPAFONE.encode("ascii")
    files["README.txt"] = LICENCE_INDEX.encode("ascii")
    return dict(sorted(files.items()))


MIT_HIPPAFONE = """\
MIT License

Copyright (c) 2026 Elizavetta (Leeza) Gay

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

LICENCE_INDEX = """\
HippaFone: which licence covers which file
==========================================

This is the list of every file the HippaFone setup script puts on an Adafruit ESP32-S3
Feather (product 5477), or into its flash memory, with the licence that covers it and where it
came from. The licence texts are in this folder (/licenses on the Feather). Run the setup script
with --licenses to print this list on the computer.

Licence texts in this folder
----------------------------
  MIT-HippaFone.txt            MIT, Copyright (c) 2026 Elizavetta (Leeza) Gay
  MIT-TinyUF2.txt              MIT, Copyright (c) 2020 Ha Thach (TinyUF2)
  MIT-MicroPython.txt          MIT, Copyright (c) 2013-2026 Damien P. George and others (MicroPython)
  micropython-lib-LICENSE.txt  MIT, micropython-lib contributors
  MIT-adafruit_hx8357.txt      MIT, Copyright (c) 2019 Melissa LeBlanc-Williams for Adafruit Industries
  MIT-st7789py.txt             MIT, Copyright (c) 2020-2023 Russ Hughes, (c) 2019 Ivan Belokobylskiy
  OFL-1.1-Terminus.txt         SIL Open Font License 1.1, Copyright (C) 2018 Dimitar Toshkov Zhekov
  Apache-2.0-AnimatedGIF.txt   Apache License 2.0, Copyright 2020 BitBank Software, Inc.
  README.txt                   this list

In the Feather's flash memory (not files you can see)
------------------------------------------------------
  TinyUF2 bootloader: bootloader.bin (0x0), partition-table.bin (0x8000), ota_data_initial.bin
  (0xE000, replaced by the setup script's own start-up choice), tinyuf2.bin (0x2D0000)
      Licence: MIT-TinyUF2.txt. TinyUF2 0.36.0 for the Feather ESP32-S3 from Adafruit,
      https://github.com/adafruit/tinyuf2/releases/tag/0.36.0 . It also contains parts of other
      projects (for example Espressif's ESP-IDF); their licences are listed in that repository.
  MicroPython firmware (ESP32_GENERIC_S3, v1.29.0) at 0x10000
      Licence: MIT-MicroPython.txt. From https://micropython.org/download/ESP32_GENERIC_S3/
      (source: https://github.com/micropython/micropython/tree/v1.29.0 ). It contains parts of
      other projects under their own licences, which are named in that licence file and in the
      source repository.

On the Feather's file system
----------------------------
  boot.py
      Written by MicroPython itself the first time it starts, not by the setup script.
      Licence: MIT-MicroPython.txt.
  sdcard.py
      Licence: micropython-lib-LICENSE.txt (MIT). Downloaded by the setup script from
      https://github.com/micropython/micropython-lib (commit 446038d), checked by SHA-256.
  hf_sd_fast.py
      Licence: micropython-lib-LICENSE.txt (MIT). Adapted from micropython-lib's sdcard.py.
  hf_panel_init.py
      Licence: MIT-adafruit_hx8357.txt and MIT-st7789py.txt. Display set-up tables copied
      from Adafruit_CircuitPython_HX8357 (tag 2.0.4,
      https://github.com/adafruit/Adafruit_CircuitPython_HX8357 ) and st7789py_mpy (commit 7265925,
      https://github.com/russhughes/st7789py_mpy ).
  hf_font.py
      Licence: OFL-1.1-Terminus.txt. The bitmaps are Terminus Font 6x12 (ter-u12n.bdf),
      Copyright (C) 2018 Dimitar Toshkov Zhekov, taken from
      https://github.com/adafruit/circuitpython/blob/10.3.1/tools/fonts/ter-u12n.bdf .
  hf_gif.mpy
      Licences: Apache-2.0-AnimatedGIF.txt (the GIF decoder AnimatedGIF by Larry Bank,
      https://github.com/bitbank2/AnimatedGIF ), MIT-MicroPython.txt (MicroPython's native
      module glue it links) and MIT-HippaFone.txt (our wrapper around the decoder).
  hf_display.py, hf_text.py, hf_touch.py, hf_mesh.py, hf_ble_kb.py, hf_pictures.py, hf_bmp.py,
  hf_sd.py, hf_battery.py, hf_cardkb.py, hf_settings.py, hippa.py
      Licence: MIT-HippaFone.txt (HippaFone's own files).
  licenses/ (this folder): the licence texts above and this README.txt
      The texts are copies of the licence files published by each project; MIT-HippaFone.txt and
      this README.txt are HippaFone's own (MIT-HippaFone.txt).
"""


def save_libraries(args, log):
    """Write everything install_files() would put on a Feather into a folder."""
    out = Path(args.save_libraries)
    files = library_files()
    template = carried(SETTINGS).decode("utf-8")
    turn = DEFAULT_ROTATION if args.rotation is None else args.rotation
    flip = {0: {"USB_ON_RIGHT": "False"}, 180: {"USB_ON_RIGHT": "True"}}.get(turn, {})
    files[SETTINGS] = make_settings(template, None, flip).encode("utf-8")
    files[HELPER] = make_helper(turn).encode("utf-8")
    sha = DOWNLOADS["sdcard.py"][1]
    data = from_cache(sha)
    if data is not None:
        how = "from the download cache"
    else:
        try:
            data, how = download("sdcard.py", log), "downloaded"
        except Problem as e:
            data, how = None, "NOT included (%s)" % e
    if data is not None:
        files["sdcard.py"] = data
    for name, body in licence_files().items():
        files["%s/%s" % (LICENSE_DIR, name)] = body
    for name, body in files.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    log("Wrote %d files to %s (%s%s)." % (len(files), out, "" if turn is None else "screen turned %d; " % turn,
                                           "sdcard.py " + how))
    return 0


SETTING = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$")


def make_settings(template, on_board, overrides):
    """hf_settings.py for this Feather: the repo's file (its notes and any new settings) with the
    Feather's own values kept, then the overrides."""
    keep = {}
    for line in (on_board or "").splitlines():
        m = SETTING.match(line)
        if m:
            keep[m.group(1)] = m.group(2)
    keep.update(overrides)
    out = []
    for line in template.splitlines():
        m = SETTING.match(line)
        if m and m.group(1) in keep:
            line = "%s = %s" % (m.group(1), keep[m.group(1)])
        out.append(line)
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- what is plugged in

def micropython_ports():
    return [p for p in list_ports() if p.ids() == MICROPYTHON_ID]


def circuitpython_drives():
    """Folders of CIRCUITPY drives whose boot_out.txt names an ESP32-S3."""
    found = []
    for root, _ in [(r, None) for r in _drive_roots()]:
        try:
            with open(os.path.join(root, "boot_out.txt"), encoding="utf-8", errors="replace") as f:
                text = f.read(400)
        except OSError:
            continue
        if "CircuitPython" in text and ("ESP32S3" in text or "ESP32-S3" in text):
            found.append(root)
    return found


def _drive_roots():
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetErrorMode(1)            # no "insert a disk" pop-ups for empty drives
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return ["%s:\\" % c for i, c in enumerate(string.ascii_uppercase) if mask >> i & 1 and c > "B"]
    roots = []
    for pattern in ("/media/*/*", "/run/media/*/*", "/media/*", "/mnt/*", "/Volumes/*"):
        roots += glob.glob(pattern)
    return roots


def look():
    """What the Feather is doing now: ('rom', port), ('uf2', folder), ('micropython', port),
    ('circuitpython', folder), ('other-uf2', folder) or (None, None)."""
    ports = list_ports()
    for p in ports:
        if p.ids() == ROM_ID:
            return "rom", p.device
    other = None
    for folder, info in uf2_drives():
        if is_our_tinyuf2(info):
            return "uf2", folder
        other = "%s (%s)" % (folder, (info.splitlines() or ["?"])[0].strip())
    for p in ports:
        if p.ids() == MICROPYTHON_ID:
            return "micropython", p.device
    cp = circuitpython_drives()
    if cp:
        return "circuitpython", cp[0]
    if other:
        return "other-uf2", other
    return None, None


SAY = {"rom": "ROM download mode on %s", "uf2": "the TinyUF2 drive %s",
       "micropython": "MicroPython running on %s", "circuitpython": "CircuitPython running (drive %s)",
       "other-uf2": "a UF2 drive that is not a Feather ESP32-S3: %s", None: "nothing yet"}

HOW = """
Put the Feather in download mode, one of these two ways:
  A. Double-tap RESET (two quick presses). A drive called FTHRS3BOOT opens.%s
  B. Hold BOOT down, press and let go of RESET, then let go of BOOT.
The script checks every half second and goes on by itself once it is sure. Ctrl-C stops it.
"""


def wait_for_download_mode(log, limit=600):
    log(HOW % ("\n     (On Ubuntu, click FTHRS3BOOT in the Files app so it is open.)" if os.name != "nt" else ""))
    last, same, said = None, 0, None
    end = time.monotonic() + limit
    while time.monotonic() < end:
        state = look()
        if state[0] in ("rom", "uf2") and state == last:
            same += 1
            if same >= 3:                       # seen four times in a row, 1.5 s: it is staying
                log("\nThe Feather is in %s." % (SAY[state[0]] % state[1]))
                return state
        else:
            same = 0
        last = state
        if state != said:
            said = state
            log("  seeing: %s%s" % (SAY[state[0]] % state[1] if state[0] else SAY[None],
                                    "  (not download mode yet)"
                                    if state[0] in ("micropython", "circuitpython") else ""))
        time.sleep(0.5)
    raise Problem("the Feather did not go into download mode")


def wait_for_micropython(log, limit=90):
    """The MicroPython port once the Feather has restarted into it. If it comes back as the
    TinyUF2 drive instead (its app slot not picked), MicroPython's .uf2 is copied onto that."""
    end = time.monotonic() + limit
    nagged = copied = False
    start = time.monotonic()
    uf2_since = None
    while time.monotonic() < end:
        kind, where = look()
        if kind == "micropython":
            time.sleep(1.5)                     # let it finish starting
            return where
        if kind == "rom" and not nagged and time.monotonic() - start > 6:
            nagged = True
            log("  It is still in ROM download mode. Let go of BOOT and press RESET once.")
        if kind == "uf2" and not copied:
            uf2_since = uf2_since or time.monotonic()
            if time.monotonic() - uf2_since > 3:  # the drive is staying: TinyUF2 waits for a file
                copied = True
                log("  It started the TinyUF2 bootloader instead; giving it MicroPython's .uf2 file.")
                flash_with_uf2(where, log)
        else:
            uf2_since = None
        time.sleep(0.5)
    raise Problem("MicroPython did not start. Press RESET once and run the script again.")


def otadata_for_ota_0():
    """ESP-IDF's otadata (8 KB at 0xE000) picking the app slot ota_0, where MicroPython is: one
    entry, ota_seq 1 with its CRC, state undefined. TinyUF2's own otadata is all 0xFF, which starts
    the TinyUF2 bootloader instead."""
    seq = struct.pack("<I", 1)
    entry = seq + b"\xff" * 20 + b"\xff\xff\xff\xff" + struct.pack("<I", zlib.crc32(seq, 0xFFFFFFFF))
    return entry + b"\xff" * (8192 - len(entry))


# ---------------------------------------------------------------- the steps

def flash_with_rom(port_name, args, log):
    log("Talking to the ESP32-S3's ROM loader on %s ..." % port_name)
    parts = tinyuf2_parts(log)
    app = download("micropython.app-bin", log)
    port = open_port(port_name)
    try:
        rom = Rom(port)
        rom.sync()
        chip = rom.chip_id()
        if chip is not None and chip != 9:
            raise Problem("this is not an ESP32-S3 (chip id %d)" % chip)
        rom.prepare()
        have_tinyuf2 = all(rom.same(off, data) for off, name, data in parts if name != "ota_data_initial.bin")
        if have_tinyuf2 and not args.bootloader:
            log("  TinyUF2 0.36.0 is already there.")
        else:
            log("  Putting the TinyUF2 0.36.0 bootloader on (it keeps the files partition).")
            for off, name, data in parts:
                rom.write(off, data, name, log)
        if rom.same(APP_OFFSET, app) and not args.reflash:
            log("  MicroPython %s is already in the app slot." % MP_VERSION)
        else:
            rom.write(APP_OFFSET, app, "MicroPython %s" % MP_VERSION, log)
        otadata = otadata_for_ota_0()
        if rom.same(0xE000, otadata):
            log("  The Feather already starts MicroPython's app slot.")
        else:
            rom.write(0xE000, otadata, "the start-up choice (otadata: start MicroPython)", log)
        log("  Restarting the Feather ...")
        rom.restart()
    finally:
        port.close()


def flash_with_uf2(folder, log):
    info = ""
    try:
        info = Path(folder, "INFO_UF2.TXT").read_text(encoding="ascii", errors="replace")
    except OSError:
        pass
    # INFO_UF2.TXT's "Flash Size" is the app slot's size (0x2C0000 on TinyUF2 0.36.0 for the 5477);
    # older layouts have a 1408 KB slot that MicroPython does not fit in.
    m = re.search(r"Flash Size:\s*0x([0-9A-Fa-f]+)", info)
    app_size = len(download("micropython.app-bin", log))
    too_small = int(m.group(1), 16) < app_size if m else tinyuf2_version(info) < (0, 35, 0)
    if too_small:
        raise Problem("this Feather's TinyUF2 bootloader has an app slot too small for MicroPython. "
                      "Use download mode B instead (hold BOOT, press RESET, let go of BOOT): the "
                      "script then puts TinyUF2 0.36.0 on first.")
    uf2 = download("micropython.uf2", log)
    log("Copying MicroPython %s onto %s (%d KB) ..." % (MP_VERSION, folder, len(uf2) // 1024))
    try:
        with open(os.path.join(folder, "micropython.uf2"), "wb") as f:
            for i in range(0, len(uf2), 65536):
                f.write(uf2[i:i + 65536])
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass        # the drive can vanish as the last block lands: the board is restarting
    log("  Copied; the Feather restarts by itself.")


def ensure_micropython(args, log):
    """The port of a Feather running MicroPython 1.29.0, putting it on first if needed."""
    if args.port:
        return args.port
    kind, where = look()
    if kind == "micropython" and not args.reflash and not args.bootloader:
        version = None
        try:
            port = open_port(where)
            try:
                board = Board(port)
                board.enter()
                impl, machine, version, _ = board.eval(BOARD_INFO)
                board.leave()
            finally:
                port.close()
        except Problem as e:
            log("Could not ask the board for its version (%s)." % e)
        if version == MP_VERSION:
            log("The Feather already runs MicroPython %s (%s)." % (version, where))
            return where
        log("The Feather on %s runs MicroPython %s; it needs %s." % (where, version or "?", MP_VERSION))
    elif kind == "circuitpython":
        log("The Feather runs CircuitPython (drive %s); it needs MicroPython %s." % (where, MP_VERSION))
    elif kind is None and not args.reflash and not args.bootloader:
        log("No Feather running MicroPython was found on USB.")
    if args.skip_firmware:
        raise Problem("MicroPython %s is needed first (run without --skip-firmware)" % MP_VERSION)
    log("Getting the firmware ready ...")
    download("micropython.uf2", log)
    download("micropython.app-bin", log)
    download("tinyuf2.zip", log)
    if kind not in ("rom", "uf2"):
        kind, where = wait_for_download_mode(log)
    if kind == "rom":
        flash_with_rom(where, args, log)
    else:
        if args.bootloader:
            raise Problem("--bootloader needs download mode B (hold BOOT, press RESET, let go of BOOT)")
        flash_with_uf2(where, log)
    log("Waiting for MicroPython to start ...")
    where = wait_for_micropython(log)
    log("MicroPython is running on %s." % where)
    return where


def prepare_libraries(args, log):
    """({board name: bytes}, hf_settings.py template): the carried libraries plus sdcard.py."""
    files = library_files()
    files["sdcard.py"] = download("sdcard.py", log)       # from micropython-lib itself
    for name, body in licence_files().items():
        files["%s/%s" % (LICENSE_DIR, name)] = body
    return files, carried(SETTINGS).decode("utf-8")


def install_files(port_name, args, prepared, log):
    """The libraries, this Feather's hf_settings.py and hippa.py, and the licences, each only if
    it changed."""
    files, template = prepared
    files = dict(files)
    log("Putting the libraries and the block helper on the Feather (%s) ..." % port_name)
    port = open_port(port_name)
    try:
        board = Board(port)
        board.enter()
        impl, machine, release, free = board.eval(BOARD_INFO)
        if impl != "micropython" or "ESP32S3" not in machine.replace("-", "").upper():
            raise Problem("this is not an ESP32-S3 running MicroPython (%s, %s)" % (impl, machine))
        settings_now = board_text(board, SETTINGS)
        turn = args.rotation
        if turn is None:                                # keep what this Feather had
            m = re.search(r"^SCREEN_TURN = (\d+)", board_text(board, HELPER) or "", re.M)
            if m and int(m.group(1)) in ROTATIONS:
                turn = int(m.group(1))
            elif re.search(r"^USB_ON_RIGHT\s*=\s*True", settings_now or "", re.M):
                turn = 180
            elif settings_now is None:                  # a blank Feather: the owner's build, USB-C on the right
                turn = DEFAULT_ROTATION
            else:
                turn = 0
        # the libraries' own setting for an upside-down screen agrees with hippa.py's
        flip = {0: {"USB_ON_RIGHT": "False"}, 180: {"USB_ON_RIGHT": "True"}}.get(turn, {})
        files[SETTINGS] = make_settings(template, settings_now, flip).encode()
        files[HELPER] = make_helper(turn).encode()
        order = list(LIBRARIES) + ["sdcard.py", SETTINGS, HELPER] + sorted(n for n in files if "/" in n)
        have = board_hashes(board, order + list(OLD_HELPERS))
        todo = [n for n in order if args.force or have[n] != hashlib.sha256(files[n]).hexdigest()]
        need = sum(len(files[n]) for n in todo)
        log("  %d of %d files to copy (%d KB); screen turned %d" % (len(todo), len(order),
                                                                    (need + 1023) // 1024, turn))
        if 0 <= free < need + 32768:
            raise Problem("not enough room on the Feather: %d KB free, about %d KB needed"
                          % (free // 1024, need // 1024 + 32))
        if any("/" in n for n in todo):
            board.exec("import os\ntry:\n    os.mkdir(%r)\nexcept OSError:\n    pass" % LICENSE_DIR)
        for n in todo:
            log("  copying %-34s %6d bytes" % (n, len(files[n])))
            board_write(board, n, files[n])
        for name in OLD_HELPERS:
            if have[name]:
                board.exec("import os\nos.remove(%r)" % name)
                log("  removed %s (hippa.py has it now)" % name)
        board.leave()
    finally:
        port.close()
    log("Done. The Feather is ready.")
    log(NEXT_STEPS)


NEXT_STEPS = """
What to do next:
  1. On a computer, open %s in Chrome or Edge.
  2. Sign in.
  3. Choose the HippaFone board.
  4. Connect to the Feather over its USB cable.
  5. Build your program with the HippaFone blocks.
""" % BIPES_URL


def main(argv=None):
    doc = __doc__.split("\n")
    ap = argparse.ArgumentParser(description=doc[0], epilog="\n".join(doc[2:]),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rotation", type=int, choices=ROTATIONS,
                    help="how the screen is built in: 0 if USB-C is on the left; 180 (the default for a "
                    "Feather with nothing on it yet) if USB-C is on the right. When left out, a Feather "
                    "that already has hippa.py or hf_settings.py keeps its own value")
    ap.add_argument("--reflash", action="store_true",
                    help="put MicroPython on again even if the Feather already runs %s" % MP_VERSION)
    ap.add_argument("--bootloader", action="store_true",
                    help="also put the TinyUF2 bootloader on again (needs download mode B)")
    ap.add_argument("--skip-firmware", action="store_true", help="never touch the firmware")
    ap.add_argument("--port", help="the port of a Feather already running MicroPython (skips the "
                    "firmware check)")
    ap.add_argument("--force", action="store_true", help="copy every file, even those already the same")
    ap.add_argument("--save", metavar="FILE", help="only write the generated hippa.py to FILE")
    ap.add_argument("--save-libraries", metavar="DIR", help="only write every file the script would "
                    "install (libraries, hippa.py, hf_settings.py, DIR/licenses) into DIR; no board needed")
    ap.add_argument("--licenses", action="store_true", help="print which licence covers which file and stop")
    ap.add_argument("--list", action="store_true", help="show the ports and UF2 drives and stop")
    args = ap.parse_args(argv)
    log = print
    try:
        if args.licenses:
            sys.stdout.write(LICENCE_INDEX)
            return 0
        if args.save:
            Path(args.save).write_text(make_helper(DEFAULT_ROTATION if args.rotation is None else args.rotation), encoding="utf-8", newline="\n")
            log("wrote %s" % args.save)
            return 0
        if args.save_libraries:
            return save_libraries(args, log)
        if args.list:
            for p in list_ports():
                print(p.label())
            for folder, info in uf2_drives():
                print("%-14s UF2 drive: %s" % (folder, info.splitlines()[0] if info else "?"))
            return 0
        compile(make_helper(0), HELPER, "exec")     # a typo in the helper stops here, not on the board
        prepared = prepare_libraries(args, log)     # before any button pressing: fails early if offline
        port = ensure_micropython(args, log)
        install_files(port, args, prepared, log)
        return 0
    except Problem as e:
        print("\nProblem: %s" % e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
