# About hippa.py and its helper files

- `hippa.py`, `hippa_io.py` and `hippa_screen.py` are the HippaFone helper
  library, written for this project.
- They run on the Adafruit ESP32-S3 Feather with 4 MB flash and 2 MB PSRAM
  (product 5477): https://www.adafruit.com/product/5477
- The screen is the 3.5" capacitive TFT FeatherWing (product 5872):
  https://www.adafruit.com/product/5872
- The start-up commands in `hippa_screen.py` come from Adafruit's
  adafruit_hx8357 library: https://github.com/adafruit/Adafruit_CircuitPython_HX8357
- Licence of that library: MIT, "Copyright 2019 Melissa LeBlanc-Williams for
  Adafruit Industries". Free to use and copy.

## Not installed yet

This guide does not put these files on the board. A later guide uploads them
with the editor's Files tab.
