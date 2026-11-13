#!/usr/bin/env python3
"""Baut test_protocol.c mit dem Host-gcc und startet ihn."""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = [os.path.join(HERE, "test_logic.c"), os.path.join(HERE, "..", "ss_logic.c")]
exe = os.path.join(tempfile.gettempdir(), "ss_logic_test" + (".exe" if os.name == "nt" else ""))
subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-type-limits", "-O1", "-o", exe, *SRC], check=True)
sys.exit(subprocess.run([exe]).returncode)
