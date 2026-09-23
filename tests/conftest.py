"""Projektwurzel auf den Importpfad, damit `pytest tests/` auch ohne `python -m` die wfg_-Module findet."""
import pathlib
import sys

ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
