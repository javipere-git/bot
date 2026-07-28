"""Doble click para abrir la app (sin ventana de consola)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tradingbot.gui.app import main  # noqa: E402

raise SystemExit(main())
