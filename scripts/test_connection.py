#!/usr/bin/env python3
"""
Test Connection — Verify setup before running strategy.

Checks:
1. Environment variables loaded
2. Bot initialization
3. Binance API accessible
4. Polymarket Gamma API (market discovery)
5. WebSocket connection (optional)

Usage:
    python scripts/test_connection.py
"""

import os
import sys
import requests

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check(name, passed, detail=""):
    icon = "✅" if passed else "❌"
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))
    return passed


def main():
    print("=" * 60)
    print("🔍 POLYMARKET BOT — CONNECTION TEST")
    print("=" * 60)
    print()

    all_ok = True

    # ========================================
    # 1. Environment Variables
    # ========================================
    print("1️⃣  Environment Variables")

    pk = os.environ.get("POLY_PRIVATE_KEY", "")
    sa = os.environ.get("POLY_SAFE_ADDRESS", "")

    pk_ok = check("POLY_PRIVATE_KEY", bool(pk),
                   f"{'set (' + pk[:6] + '...' + pk[-4:] + ')' if pk else 'NOT SET'}")
    sa_ok = check("POLY_SAFE_ADDRESS", bool(sa),
                   f"{'set (' + sa[:6] + '...' + sa[-4:] + ')' if sa else 'NOT SET'}")

    # Builder (optional)
    bk = os.environ.get("POLY_BUILDER_API_KEY", "")
    bs = os.environ.get("POLY_BUILDER_API_SECRET", "")
    bp = os.environ.get("POLY_BUILDER_API_PASSPHRASE", "")
    builder_ok = bool(bk and bs and bp)
    check("Builder credentials", builder_ok,
          "gasless mode enabled" if builder_ok else "not set (will pay gas fees — OK for testing)")

    if not pk_ok or not sa_ok:
        print("\n❌ FATAL: Private key dan safe address WAJIB diisi!")
        print("   Edit .env lalu jalankan: source .env")
        return False

    print()

    # ========================================
    # 2. Dependencies
    # ========================================
    print("2️⃣  Dependencies")

    try:
        import web3
        check("web3", True, f"v{web3.__version__}")
    except ImportError:
        check("web3", False, "pip install web3")
        all_ok = False

    try:
        import eth_account
        check("eth_account", True)
    except ImportError:
        check("eth_account", False, "pip install eth-account")
        all_ok = False

    try:
        import yaml
        check("pyyaml", True)
    except ImportError:
        check("pyyaml", False, "pip install pyyaml")
        all_ok = False

    try:
        import websockets
        check("websockets", True)
    except ImportError:
        check("websockets", False, "pip install websockets")
        all_ok = False

    print()

    # ========================================
    # 3. Bot Initialization
    # ========================================
    print("3️⃣  Bot Initialization")

    try:
        from src import create_bot_from_env
        bot = create_bot_from_env()
        check("TradingBot created", True)
        check("Bot initialized", bot.is_initialized() if hasattr(bot, 'is_initialized') else True)
    except Exception as e:
        check("TradingBot created", False, str(e))
        all_ok = False

    print()

    # ========================================
    # 4. Binance API
    # ========================================
    print("4️⃣  Binance API (price data source)")

    coins = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "XRP": "XRPUSDT"}

    for coin, symbol in coins.items():
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=5"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            candles = resp.json()
            last_price = float(candles[-1][4])
            check(f"{coin} ({symbol})", True, f"${last_price:,.2f}")
        except Exception as e:
            check(f"{coin} ({symbol})", False, str(e))
            all_ok = False

    print()

    # ========================================
    # 5. Polymarket Gamma API (market discovery)
    # ========================================
    print("5️⃣  Polymarket Gamma API (market discovery)")

    try:
        from src.gamma_client import GammaClient
        gamma = GammaClient()

        for coin in ["BTC", "ETH", "SOL", "XRP"]:
            try:
                info = gamma.get_market_info(coin)
                if info:
                    up_p = info['prices']['up']
                    down_p = info['prices']['down']
                    accepting = info.get('accepting_orders', False)
                    check(f"{coin} 15-min market", True,
                          f"UP:{up_p:.0%} DOWN:{down_p:.0%} {'✅ accepting' if accepting else '⏸ not accepting'}")
                else:
                    check(f"{coin} 15-min market", False, "no active market right now")
            except Exception as e:
                check(f"{coin} 15-min market", False, str(e))

    except Exception as e:
        check("GammaClient", False, str(e))
        all_ok = False

    print()

    # ========================================
    # 6. CLOB API
    # ========================================
    print("6️⃣  Polymarket CLOB API")

    try:
        resp = requests.get("https://clob.polymarket.com/time", timeout=10)
        resp.raise_for_status()
        check("CLOB API reachable", True, f"server time OK")
    except Exception as e:
        check("CLOB API reachable", False, str(e))
        all_ok = False

    print()

    # ========================================
    # SUMMARY
    # ========================================
    print("=" * 60)
    if all_ok:
        print("🟢 ALL CHECKS PASSED — ready to run!")
        print()
        print("Next step:")
        print("  python scripts/run_fair_value.py")
    else:
        print("🔴 SOME CHECKS FAILED — fix issues above")
        print()
        print("Common fixes:")
        print("  pip install -r requirements.txt     # install dependencies")
        print("  cp .env.example .env && nano .env   # setup credentials")
        print("  source .env                         # load env vars")
    print("=" * 60)

    return all_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
