"""
Verificacion de la llave de sandbox (Fase 2 - solo lectura).

Hace UNICAMENTE llamadas de lectura contra el sandbox de Tradier:
NO manda, modifica ni cancela ninguna orden. No toca dinero (es paper).

Sirve para confirmar que la llave funciona y que vemos la cuenta.

Para correrlo:  python examples/verificar_sandbox.py
"""
from __future__ import annotations

import configparser
import os
import sys

try:
    import requests
except ImportError:
    sys.exit("Falta la libreria 'requests'. Instalala con:  pip install requests")

BASE = "https://sandbox.tradier.com/v1"  # SANDBOX: dinero simulado


def cargar_credenciales() -> tuple[str, str]:
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta = os.path.join(raiz, "config", "credentials.ini")
    cfg = configparser.ConfigParser()
    if not cfg.read(ruta):
        sys.exit(f"No encontre el archivo de credenciales: {ruta}")
    return cfg["tradier"]["sandbox_token"], cfg["tradier"]["sandbox_account_id"]


def main() -> None:
    token, account_id = cargar_credenciales()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    print("Probando la llave de SANDBOX (solo lectura, no toca dinero)...")
    print("-" * 60)

    # 1) Perfil del usuario (lectura)
    r = requests.get(f"{BASE}/user/profile", headers=headers, timeout=15)
    print(f"GET /user/profile  ->  HTTP {r.status_code}")
    if r.status_code == 200:
        perfil = r.json().get("profile", {})
        print(f"   usuario: {perfil.get('name', '(sin nombre)')}")

    # 2) Saldos de la cuenta paper (lectura)
    r2 = requests.get(
        f"{BASE}/accounts/{account_id}/balances", headers=headers, timeout=15
    )
    print(f"GET /accounts/{account_id}/balances  ->  HTTP {r2.status_code}")
    if r2.status_code == 200:
        bal = r2.json().get("balances", {})
        print(f"   tipo de cuenta: {bal.get('account_type', '?')}")
        print(f"   plata total (virtual): USD {bal.get('total_equity', '?')}")
        print(f"   efectivo (virtual):    USD {bal.get('total_cash', '?')}")
    else:
        print(f"   respuesta: {r2.text[:300]}")

    # 3) Mostrar el cupo de rate limit que devuelve la propia API
    print("-" * 60)
    print("Cupo de la API (lo informa Tradier en cada respuesta):")
    for h in ("X-Ratelimit-Allowed", "X-Ratelimit-Used", "X-Ratelimit-Available"):
        if h in r2.headers:
            print(f"   {h}: {r2.headers[h]}")

    print("-" * 60)
    if r.status_code == 200 or r2.status_code == 200:
        print("OK: la llave de sandbox funciona.")
    else:
        print("Algo no anduvo: revisa la llave o el numero de cuenta arriba.")


if __name__ == "__main__":
    main()
