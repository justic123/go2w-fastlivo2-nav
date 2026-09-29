#!/usr/bin/env python3
"""Idempotent Nav2 service API (starting services does not enable motion)."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'lifecycle'))
from service_core import main
main('nav')
