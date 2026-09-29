#!/usr/bin/env python3
"""Idempotent capture API; status never waits for locks, stop never waits for exports."""
import sys
from pathlib import Path
base=Path(__file__).resolve().parent
sys.path.insert(0,str((base if (base/'lifecycle').is_dir() else base.parent)/'lifecycle'))
from service_core import main
main('capture')
