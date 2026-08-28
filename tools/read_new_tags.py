#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reads RFID tags and prints each unique tag id once — used to collect the
# ids of new tags before registering them in the database.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rfid_reader import RFIDReader

reader = RFIDReader()
print("Ready — bring a tag close to the RFID reader...")
print("Ctrl+C to exit.\n")

try:
    seen = set()
    while True:
        tag = reader.wait_for_tag()
        if tag not in seen:
            seen.add(tag)
            print(f"[TAG] {tag}")
        else:
            pass  # same tag still near the reader, ignore the repeat
except KeyboardInterrupt:
    print(f"\n\nTotal: {len(seen)} tags read.")
    for t in sorted(seen):
        print(f"  {t}")
finally:
    reader.close()
