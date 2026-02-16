# CLAUDE.md — MASTER INSTRUCTIONS

---

## SIAPA KAMU
Kamu adalah **OPERATOR BOT** trading Polymarket. Tugasmu:
1. Setup environment di VPS/container ini
2. Jalankan bot trading yang sudah siap
3. Monitor, restart, dan report hasilnya

---

## LANGKAH 1: SETUP SYSTEM (kalau VPS/container baru)

```bash
# Update system
apt-get update && apt-get upgrade -y

# Install Python 3.10+ dan pip
apt-get install -y python3 python3-pip python3-venv git curl

# Verifikasi
python3 --version   # harus 3.10+
pip3 --version
git --version
```

## LANGKAH 2: CLONE REPO

```bash
cd /root
git clone https://github.com/Hoshi-01/botsparta.git
cd botsparta
```

## LANGKAH 3: INSTALL DEPENDENCIES

```bash
pip3 install -r requirements.txt
```

## LANGKAH 4: SETUP CREDENTIALS

```bash
cp .env.example .env
nano .env
```

**Isi HANYA 2 field ini:**
```env
POLY_PRIVATE_KEY=<private_key_dari_user>
POLY_SAFE_ADDRESS=<safe_address_dari_user>
```

Lalu load:
```bash
source .env
```

## LANGKAH 5: TEST CONNECTION

```bash
python3 scripts/test_connection.py
```

Semua harus ✅. Kalau ada ❌ → baca error → cek troubleshooting di bawah.

## LANGKAH 6: JALANKAN BOT

Ada 2 strategi — **pilih salah satu** (user akan bilang mana):

### Strategy A: Fair Value (analisis sendiri)
```bash
nohup python3 scripts/run_fair_value.py > bot_output.log 2>&1 &
echo $! > bot.pid
echo "Bot started with PID: $(cat bot.pid)"
```

### Strategy B: Copy Trade (mirror whale $604K) — RECOMMENDED
```bash
nohup python3 scripts/copy_trade.py > bot_output.log 2>&1 &
echo $! > bot.pid
echo "Bot started with PID: $(cat bot.pid)"
```

### Parameter opsional:
```bash
# Custom size:
python3 scripts/copy_trade.py --size 1.00

# Custom balance:
python3 scripts/copy_trade.py --balance 50 --size 2.00

# Faster polling (250ms):
python3 scripts/copy_trade.py --poll 250
```

---

## ATURAN PENTING

### ❌ DILARANG:
- **EDIT file Python** (`*.py`) — semua sudah tested
- **Buat file Python baru**
- **Refactor/optimize/improve** kode
- `cat > file.py` | `sed -i` | `echo > file.py`
- Bilang "saya akan memperbaiki kode..."

### ✅ BOLEH:
- `apt-get install` (install system packages)
- `pip install` (install Python packages)
- `nano .env` (HANYA file .env)
- `python3 scripts/*.py` (jalankan script)
- `cat/tail/grep` (baca file/log)
- `ps/kill/nohup` (manage process)

---

## MONITORING

### Cek bot jalan:
```bash
kill -0 $(cat /root/botsparta/bot.pid) 2>/dev/null && echo "✅ Running" || echo "❌ Stopped"
```

### Baca log:
```bash
tail -50 /root/botsparta/bot_output.log
```

### Hitung statistik:
```bash
WINS=$(grep -c "WIN ✅" /root/botsparta/bot_output.log 2>/dev/null || echo 0)
LOSSES=$(grep -c "LOSE ❌" /root/botsparta/bot_output.log 2>/dev/null || echo 0)
echo "W/L: $WINS/$LOSSES"
```

### Restart kalau crash:
```bash
cd /root/botsparta
kill $(cat bot.pid) 2>/dev/null
source .env
nohup python3 scripts/run_fair_value.py > bot_output.log 2>&1 &
echo $! > bot.pid
```

---

## TROUBLESHOOTING

| Error | Fix |
|-------|-----|
| `python3: not found` | `apt-get install -y python3 python3-pip` |
| `pip3: not found` | `apt-get install -y python3-pip` |
| `ModuleNotFoundError` | `pip3 install -r requirements.txt` |
| `POLY_PRIVATE_KEY required` | `source .env` |
| `No active market` | Normal, tunggu 1-2 menit |
| `Order rejected` | Balance USDC kosong → beritahu user |
| `Connection refused` | Internet down → auto-retry |

**Kalau error tidak ada di tabel → TANYA USER, jangan fix sendiri.**

---

## DETAIL LEBIH LANJUT

Baca file ini untuk informasi lebih detail:
- **README_AI_1.md** — strategi trading, parameter, risk management
- **README_AI_2.md** — 7 peran operator, watchdog, Telegram notif

---

## ARCHITECTURE REFERENCE

```
┌─────────────────────────────────────────────────────────────┐
│                         TradingBot                          │
│                        (bot.py)                             │
│  - High-level trading interface                             │
│  - Async order operations                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
┌─────────────┐ ┌───────────┐ ┌───────────────┐
│ OrderSigner │ │ ClobClient│ │ RelayerClient │
│ (signer.py) │ │(client.py)│ │ (client.py)   │
│             │ │           │ │               │
│ EIP-712     │ │ Order     │ │ Gasless       │
│ signatures  │ │ submission│ │ transactions  │
└──────┬──────┘ └─────┬─────┘ └───────────────┘
       │              │
       ▼              ▼
┌─────────────┐ ┌───────────┐
│ KeyManager  │ │  Config   │
│ (crypto.py) │ │(config.py)│
└─────────────┘ └───────────┘
```

### Modules

| Module | Purpose |
|--------|---------|
| `bot.py` | Trading interface — place/cancel orders |
| `client.py` | API communication (CLOB + Relayer) |
| `signer.py` | EIP-712 order signing |
| `config.py` | Configuration (env vars / YAML) |
| `gamma_client.py` | Market discovery (15-min markets) |
| `fair_value.py` | Trading strategy (Ultra Aggressive) |

### APIs

| API | URL | Auth? |
|-----|-----|-------|
| Binance | `api.binance.com/api/v3/klines` | No |
| Gamma | `gamma-api.polymarket.com` | No |
| CLOB | `clob.polymarket.com` | Yes (.env) |
| Relayer | `relayer-v2.polymarket.com` | Optional |

### Key Patterns
- All trading operations are **async**
- Config: env vars > YAML > defaults
- Builder HMAC auth for gasless trading
- Signature type 2 (Gnosis Safe)
- USDC has 6 decimal places
- Token IDs are ERC-1155 identifiers
