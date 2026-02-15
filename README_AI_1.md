# 🤖 README AI — Part 1: Setup & Run Guide
# For AI Agents (OpenClaw, Claude, GPT, Gemini)

> **MODE: ULTRA AGGRESSIVE**
> Modal: $10 | Size: FIXED $0.50 | Threshold: 0.02% | Coins: BTC+ETH+SOL+XRP
> **Setup hanya butuh 2 credential: PRIVATE_KEY + SAFE_ADDRESS**

---

## KAMU HANYA PERLU 3 LANGKAH

### LANGKAH 1: Setup Environment

```bash
cd /path/to/polymarket-trading-bot

# Install dependencies
pip install -r requirements.txt

# Setup credentials
cp .env.example .env
nano .env   # isi 2 field WAJIB di bawah
```

Isi `.env` — **HANYA 2 FIELD WAJIB:**
```env
# === WAJIB (tanpa ini bot TIDAK bisa jalan) ===
POLY_PRIVATE_KEY=<private_key_metamask_64_hex>
POLY_SAFE_ADDRESS=<polymarket_proxy_wallet_address>

# === OPSIONAL (untuk gasless trading, bisa ditambah nanti) ===
# POLY_BUILDER_API_KEY=
# POLY_BUILDER_API_SECRET=
# POLY_BUILDER_API_PASSPHRASE=
```

> **Catatan:** Tanpa Builder credentials, bot tetap bisa trading tapi bayar gas fee Polygon (~$0.01/tx). Untuk setup awal ini OK. Builder credentials bisa ditambahkan nanti dari polymarket.com/settings?tab=builder.

Load env:
```bash
source .env
```

### LANGKAH 2: Test Connection (CEK DULU)

```bash
python scripts/test_connection.py
```

Script ini akan cek:
- ✅ Environment variables loaded
- ✅ Dependencies installed
- ✅ Bot initialized
- ✅ Binance API accessible (harga realtime)
- ✅ Polymarket Gamma API (market discovery)
- ✅ CLOB API reachable

**JANGAN lanjut ke langkah 3 kalau ada yang ❌ FAILED.**

### LANGKAH 3: Jalankan Bot

```bash
# Default: $10 modal, $0.50/trade, Ultra Aggressive
python scripts/run_fair_value.py

# Custom modal:
python scripts/run_fair_value.py --balance 50 --size 1.00

# Phase 2 (compound, setelah validasi):
python scripts/run_fair_value.py --balance 100 --phase2 --pct 3
```

**Selesai.** Bot akan jalan otomatis 24/7.

---

## APA YANG BOT LAKUKAN

### Strategi: Fair Value Edge (Ultra Aggressive)

Setiap 15 menit:
1. **Cek harga crypto** di Binance (gratis, realtime)
2. **Hitung fair value** — apakah UP atau DOWN lebih mungkin
3. **Bandingkan** dengan harga Polymarket
4. **Beli sisi yang underpriced** jika ada edge ≥ 0.5%
5. **Scan semua coin**: BTC → ETH → SOL → XRP
6. **Max 2 trade per window** (bisa BTC + ETH sekaligus)

### Parameter Ultra:
| Setting | Nilai |
|---------|-------|
| Signal threshold | **0.02%** (super sensitif) |
| Min edge | **0.5%** (minimal mispricing) |
| Coins | **BTC, ETH, SOL, XRP** (semua) |
| Trades per window | **Max 2** |
| Max trades/jam | **~8** |
| Max trades/hari | **~150+** |
| Size | **$0.50 fixed** (Phase 1) |

### Fair Value Map:
```
Binance perubahan 5 menit → Fair Value UP:
  > +0.30%  → 75%
  > +0.20%  → 70%
  > +0.15%  → 65%
  > +0.10%  → 60%
  > +0.05%  → 57%
  > +0.02%  → 54%    ← signal terkecil (ULTRA)
  ±0.02%   → SKIP    ← dead zone
  < -0.02%  → 46%    (fair DOWN = 54%)
  < -0.05%  → 43%
  < -0.10%  → 40%
  < -0.15%  → 35%
  < -0.20%  → 30%
  < -0.30%  → 25%
```

---

## RISK MANAGEMENT (OTOMATIS)

| Rule | Aksi |
|------|------|
| Daily loss ≥ $2.00 | STOP sampai besok |
| 5 loss berturut | Cooldown 30 menit |
| Balance < $8.00 | **STOP TOTAL** |
| API error 3x berturut | Halt, tunggu reconnect |
| Spread > 20¢ | Skip trade itu |

---

## MONITORING

Bot otomatis log:
- Setiap trade → detail lengkap (coin, side, price, edge, result)
- Setiap market change (15 min) → window summary
- Setiap jam → hourly report
- Setiap hari → daily report

### Contoh output:
```
[TRADE #1] BTC | BUY UP | Price: 48% | Shares: 1.04 | Cost: $0.50 | Edge: +6.0% | Binance: +0.15%
[WIN ✅] +$0.54 | Balance: $10.54 | WR: 100.0% (1/1)

[TRADE #2] ETH | BUY DOWN | Price: 45% | Shares: 1.11 | Cost: $0.50 | Edge: +1.0% | Binance: -0.08%
[LOSE ❌] -$0.50 | Balance: $10.04 | WR: 50.0% (1/2)

[HOURLY REPORT] 01:00 UTC
  Trades: 6 | W/L: 4/2 | WR: 66.7% | P&L: +$1.08 | Balance: $11.08
```

---

## PHASE SYSTEM

| Phase | Kapan | Size | Tujuan |
|-------|-------|------|--------|
| **Phase 1** (sekarang) | 0-100 trades | FIXED $0.50 | Validasi win rate >60% |
| **Phase 2** | Setelah Phase 1 profit | 3% balance | Compound growth |

Switch ke Phase 2:
```bash
python scripts/run_fair_value.py --balance <saldo_sekarang> --phase2 --pct 3
```

---

## TROUBLESHOOTING

| Masalah | Solusi |
|---------|--------|
| "Bot initialization failed" | Cek `.env` — semua field wajib diisi |
| "No active market" | Market 15-min belum dimulai, tunggu 1-2 menit |
| "Order failed" | Cek balance USDC di Polymarket wallet |
| Tidak ada trade 1 jam | Normal jika semua sideways. Threshold 0.02% sudah ultra sensitif |
| "Daily loss limit" | Bot auto-stop, akan reset besok |

---

## PERINGATAN

> ⚠️ **JANGAN:** Trade lebih dari $0.50 per trade di Phase 1 | Ubah parameter tanpa instruksi manusia | Abaikan risk rules
>
> ✅ **SELALU:** Log setiap trade | Report hourly/daily | Stop kalau balance < $8
