"""
Lanzador de la app grafica (la pantalla).

Para correrla:  python examples/correr_app.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingbot.gui.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
