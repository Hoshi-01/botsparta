#!/usr/bin/env python3
"""
Copy Trade Bot — Mirror trades from a Polymarket whale in milliseconds.

Target: 0x8c74b4eef9a894433B8126aA11d1345efb2B0488
Profile: https://polymarket.com/@k9Q2mX4L8A7ZP3R
Stats: +$604,800 profit | 16,662 predictions | BTC/ETH Up/Down 15-min

USAGE:
    python scripts/copy_trade.py                          # Default $0.50/trade
    python scripts/copy_trade.py --size 1.00              # $1.00/trade
    python scripts/copy_trade.py --size 2.00 --delay 0    # $2/trade, 0ms delay

REQUIREMENTS:
    - .env with POLY_PRIVATE_KEY + POLY_SAFE_ADDRESS
    - pip install -r requirements.txt
"""

import asyncio
import time
import sys
import os
import argparse
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, List, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import create_bot_from_env
from src.gamma_client import GammaClient


# ============================================================
# CONFIG
# ============================================================

# Target whale to copy
TARGET_ADDRESS = "0x8c74b4eef9a894433B8126aA11d1345efb2B0488"

# Polymarket Data API
DATA_API = "https://data-api.polymarket.com"

# CLOB API
CLOB_API = "https://clob.polymarket.com"

# Poll interval in seconds (lower = faster detection, but more API calls)
POLL_INTERVAL_MS = 500  # 500ms = 0.5 seconds


# ============================================================
# TRADE MONITOR
# ============================================================

class CopyTradeBot:
    """
    Monitor a whale's trades and copy them in milliseconds.
    
    Flow:
    1. Poll Data API every 500ms for new trades
    2. Detect new trades by comparing with last known trade
    3. Immediately mirror the trade on our account
    4. Log everything
    """
    
    def __init__(self, bot, size_usd: float = 0.50, delay_ms: int = 0,
                 max_daily_loss: float = 2.00, min_balance: float = 8.00):
        self.bot = bot
        self.size_usd = size_usd
        self.delay_ms = delay_ms
        self.max_daily_loss = max_daily_loss
        self.min_balance = min_balance
        
        self.gamma = GammaClient()
        self.balance = 10.0
        self.seen_trades: Set[str] = set()
        self.last_trade_id: Optional[str] = None
        
        # Stats
        self.total_copies = 0
        self.wins = 0
        self.losses = 0
        self.skips = 0
        self.daily_loss = 0.0
        self.errors = 0
        
        # Session for connection pooling (faster HTTP)
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "PolymarketBot/1.0",
        })
    
    def log(self, msg: str):
        """Timestamped logging."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{ts}] {msg}")
    
    # ========================================
    # FETCH WHALE TRADES
    # ========================================
    
    def fetch_whale_trades(self, limit: int = 5) -> Optional[List[Dict]]:
        """
        Fetch latest trades from the whale.
        Returns list of trades, newest first.
        """
        try:
            url = f"{DATA_API}/activity"
            params = {
                "user": TARGET_ADDRESS,
                "type": "TRADE",
                "limit": limit,
                "sortDirection": "desc",
            }
            resp = self.session.get(url, params=params, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            
            # Data API may return different structures
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "history" in data:
                return data["history"]
            elif isinstance(data, dict) and "data" in data:
                return data["data"]
            return data if isinstance(data, list) else []
            
        except Exception as e:
            self.errors += 1
            if self.errors <= 3:
                self.log(f"[ERROR] Fetch trades: {e}")
            return None
    
    def fetch_whale_trades_clob(self, limit: int = 5) -> Optional[List[Dict]]:
        """
        Alternative: Fetch trades via CLOB API.
        """
        try:
            url = f"{CLOB_API}/data/trades"
            params = {
                "maker_address": TARGET_ADDRESS,
                "limit": limit,
            }
            resp = self.session.get(url, params=params, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return None
    
    # ========================================
    # DETECT NEW TRADE
    # ========================================
    
    def detect_new_trades(self, trades: List[Dict]) -> List[Dict]:
        """
        Compare with seen trades, return only new ones.
        """
        new_trades = []
        
        for trade in trades:
            # Extract trade ID (could be tx hash, trade ID, or timestamp)
            trade_id = (
                trade.get("id") or 
                trade.get("tradeId") or 
                trade.get("transactionHash") or
                trade.get("timestamp", "") + str(trade.get("price", ""))
            )
            
            if trade_id and trade_id not in self.seen_trades:
                self.seen_trades.add(trade_id)
                new_trades.append(trade)
        
        # Keep seen_trades from growing forever
        if len(self.seen_trades) > 1000:
            # Keep only last 500
            self.seen_trades = set(list(self.seen_trades)[-500:])
        
        return new_trades
    
    # ========================================
    # PARSE TRADE INFO
    # ========================================
    
    def parse_trade(self, trade: Dict) -> Optional[Dict]:
        """
        Parse a whale trade into actionable info.
        Returns: {side, token_id, price, market, coin, outcome} or None
        """
        try:
            # Try different field names from Data API
            side = (
                trade.get("side") or 
                trade.get("type") or 
                trade.get("action", "")
            ).upper()
            
            # Normalize side
            if side in ("BUY", "BOUGHT"):
                side = "BUY"
            elif side in ("SELL", "SOLD"):
                side = "SELL"
            else:
                side = "BUY"  # Default to BUY for copy
            
            # Get token/market info
            token_id = (
                trade.get("asset") or
                trade.get("tokenId") or
                trade.get("token_id") or
                trade.get("assetId") or
                ""
            )
            
            price = float(
                trade.get("price") or
                trade.get("avgPrice") or
                trade.get("average_price") or
                0.50
            )
            
            # Get market/outcome info
            market = (
                trade.get("market") or
                trade.get("slug") or
                trade.get("title") or
                trade.get("question") or
                ""
            )
            
            outcome = (
                trade.get("outcome") or
                trade.get("outcomeName") or
                ""
            )
            
            # Try to detect coin
            coin = "UNKNOWN"
            market_lower = market.lower()
            if "btc" in market_lower or "bitcoin" in market_lower:
                coin = "BTC"
            elif "eth" in market_lower or "ethereum" in market_lower:
                coin = "ETH"
            elif "sol" in market_lower or "solana" in market_lower:
                coin = "SOL"
            elif "xrp" in market_lower:
                coin = "XRP"
            
            return {
                "side": side,
                "token_id": token_id,
                "price": price,
                "market": market,
                "coin": coin,
                "outcome": outcome,
                "raw": trade,
            }
        except Exception as e:
            self.log(f"[ERROR] Parse trade: {e}")
            return None
    
    # ========================================
    # EXECUTE COPY TRADE
    # ========================================
    
    async def execute_copy(self, trade_info: Dict):
        """
        Mirror a whale's trade on our account.
        """
        side = trade_info["side"]
        price = trade_info["price"]
        token_id = trade_info["token_id"]
        coin = trade_info["coin"]
        outcome = trade_info["outcome"]
        market = trade_info["market"]
        
        # Only copy BUY trades (we follow the whale's buys)
        if side != "BUY":
            self.log(f"[SKIP] Whale SELL — we don't copy sells")
            self.skips += 1
            return
        
        # Validate price
        if price <= 0 or price >= 1.0:
            self.log(f"[SKIP] Invalid price: {price}")
            self.skips += 1
            return
        
        # Risk check
        if self.daily_loss >= self.max_daily_loss:
            self.log(f"[STOP] Daily loss ${self.daily_loss:.2f} >= ${self.max_daily_loss}")
            return
        
        if self.balance < self.min_balance:
            self.log(f"[STOP] Balance ${self.balance:.2f} < ${self.min_balance}")
            return
        
        # If no token_id from API, try to find it via GammaClient
        if not token_id and coin != "UNKNOWN":
            try:
                info = self.gamma.get_market_info(coin)
                if info:
                    outcome_lower = outcome.lower()
                    if "up" in outcome_lower or "yes" in outcome_lower:
                        token_id = info["token_ids"]["up"]
                    elif "down" in outcome_lower or "no" in outcome_lower:
                        token_id = info["token_ids"]["down"]
                    else:
                        token_id = info["token_ids"]["up"]  # default
            except Exception:
                pass
        
        if not token_id:
            self.log(f"[SKIP] Cannot find token_id for {coin} {outcome}")
            self.skips += 1
            return
        
        # Calculate shares
        shares = self.size_usd / price
        
        # Optional delay
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000)
        
        # EXECUTE
        self.total_copies += 1
        t_start = time.time()
        
        try:
            result = await self.bot.place_order(
                token_id=token_id,
                price=price,
                size=shares,
                side="BUY",
            )
            
            t_ms = (time.time() - t_start) * 1000
            
            if result and getattr(result, 'success', True):
                self.log(
                    f"[COPY #{self.total_copies}] ✅ {coin} {outcome} | "
                    f"Price: {price:.0%} | Shares: {shares:.2f} | "
                    f"Cost: ${self.size_usd:.2f} | "
                    f"Exec: {t_ms:.0f}ms | "
                    f"Market: {market[:50]}"
                )
            else:
                self.log(f"[COPY #{self.total_copies}] ❌ Order failed: {result}")
                self.errors += 1
                
        except Exception as e:
            t_ms = (time.time() - t_start) * 1000
            self.log(f"[COPY #{self.total_copies}] ❌ Error ({t_ms:.0f}ms): {e}")
            self.errors += 1
    
    # ========================================
    # MAIN LOOP
    # ========================================
    
    async def run(self):
        """Main copy trading loop — polls every 500ms."""
        
        self.log("=" * 60)
        self.log("🐋 COPY TRADE BOT — WHALE MIRROR")
        self.log("=" * 60)
        self.log(f"  Target: {TARGET_ADDRESS[:10]}...{TARGET_ADDRESS[-6:]}")
        self.log(f"  Size: ${self.size_usd:.2f}/trade")
        self.log(f"  Poll: {POLL_INTERVAL_MS}ms")
        self.log(f"  Delay: {self.delay_ms}ms")
        self.log(f"  Balance: ${self.balance:.2f}")
        self.log("=" * 60)
        
        # Initial load — mark existing trades as "seen"
        self.log("[INIT] Loading existing trades...")
        initial = self.fetch_whale_trades(limit=20)
        if initial:
            for trade in initial:
                trade_id = (
                    trade.get("id") or 
                    trade.get("tradeId") or 
                    trade.get("transactionHash") or
                    trade.get("timestamp", "") + str(trade.get("price", ""))
                )
                if trade_id:
                    self.seen_trades.add(trade_id)
            self.log(f"[INIT] Loaded {len(self.seen_trades)} existing trades (will not copy these)")
        else:
            self.log("[INIT] No existing trades found or API error — starting fresh")
        
        self.log("[READY] Watching for whale trades...")
        self.log("")
        
        poll_count = 0
        last_report = time.time()
        
        while True:
            try:
                # Risk check
                if self.balance < self.min_balance:
                    self.log(f"[HALT] Balance ${self.balance:.2f} < ${self.min_balance}")
                    break
                
                if self.daily_loss >= self.max_daily_loss:
                    self.log(f"[PAUSE] Daily loss limit. Waiting 1 hour...")
                    await asyncio.sleep(3600)
                    self.daily_loss = 0
                    continue
                
                # Fetch latest trades
                trades = self.fetch_whale_trades(limit=5)
                
                if trades:
                    new_trades = self.detect_new_trades(trades)
                    
                    for trade in reversed(new_trades):  # Process oldest first
                        trade_info = self.parse_trade(trade)
                        
                        if trade_info:
                            self.log(
                                f"[DETECTED] 🐋 Whale trade: {trade_info['coin']} "
                                f"{trade_info['outcome']} {trade_info['side']} "
                                f"@ {trade_info['price']:.0%}"
                            )
                            await self.execute_copy(trade_info)
                
                # Periodic status report
                poll_count += 1
                now = time.time()
                if now - last_report >= 300:  # Every 5 minutes
                    self.log(
                        f"[STATUS] Polls: {poll_count} | "
                        f"Copies: {self.total_copies} | "
                        f"W/L: {self.wins}/{self.losses} | "
                        f"Skips: {self.skips} | "
                        f"Errors: {self.errors} | "
                        f"Balance: ${self.balance:.2f}"
                    )
                    last_report = now
                
                # Wait before next poll
                await asyncio.sleep(POLL_INTERVAL_MS / 1000)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.log(f"[ERROR] Loop error: {e}")
                self.errors += 1
                await asyncio.sleep(2)  # Brief pause on error
        
        # Final report
        self.log("")
        self.log("=" * 60)
        self.log("📋 FINAL REPORT")
        self.log("=" * 60)
        self.log(f"  Total copies: {self.total_copies}")
        self.log(f"  Wins/Losses: {self.wins}/{self.losses}")
        self.log(f"  Skips: {self.skips}")
        self.log(f"  Errors: {self.errors}")
        self.log(f"  Balance: ${self.balance:.2f}")
        self.log("=" * 60)


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Copy Trade Bot — Mirror a Polymarket whale")
    parser.add_argument("--size", type=float, default=0.50, help="Trade size in USDC (default: 0.50)")
    parser.add_argument("--balance", type=float, default=10.0, help="Starting balance (default: 10)")
    parser.add_argument("--delay", type=int, default=0, help="Delay before copy in ms (default: 0)")
    parser.add_argument("--poll", type=int, default=500, help="Poll interval ms (default: 500)")
    parser.add_argument("--max-daily-loss", type=float, default=2.00, help="Max daily loss (default: 2.00)")
    parser.add_argument("--target", type=str, default=TARGET_ADDRESS, help="Target wallet to copy")
    return parser.parse_args()


async def main():
    args = parse_args()
    
    global TARGET_ADDRESS, POLL_INTERVAL_MS
    TARGET_ADDRESS = args.target
    POLL_INTERVAL_MS = args.poll
    
    # Init bot
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    try:
        bot = create_bot_from_env()
    except Exception as e:
        print(f"❌ Bot init failed: {e}")
        print("Pastikan .env sudah diisi!")
        return
    
    # Create copy trader
    copier = CopyTradeBot(
        bot=bot,
        size_usd=args.size,
        delay_ms=args.delay,
        max_daily_loss=args.max_daily_loss,
    )
    copier.balance = args.balance
    
    # Run
    try:
        await copier.run()
    except KeyboardInterrupt:
        print("\n⏹ Stopped")


if __name__ == "__main__":
    asyncio.run(main())
