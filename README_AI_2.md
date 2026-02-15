# 🤖 README AI — Part 2: Agent Operations Guide
# Peran kamu sebagai AI Agent: Operator, Monitor, Maintainer

> **Kamu = Operator Bot. Bukan trader.**
> Bot Python yang trading. Kamu yang setup, monitor, fix, dan upgrade.

---

## PERAN 1: SETUP & DEPLOY

### Pertama kali (sekali saja):
```bash
cd /path/to/polymarket-trading-bot

# 1. Install
pip install -r requirements.txt

# 2. Setup credentials (HANYA 2 FIELD WAJIB)
cp .env.example .env
# Edit .env → isi POLY_PRIVATE_KEY dan POLY_SAFE_ADDRESS
nano .env

# 3. Load
source .env

# 4. Test koneksi
python scripts/test_connection.py

# 5. Jalankan bot di background (tetap jalan walau terminal ditutup)
nohup python scripts/run_fair_value.py > bot_output.log 2>&1 &
echo $! > bot.pid
echo "Bot started with PID: $(cat bot.pid)"
```

---

## PERAN 2: MONITORING (RUTIN)

### Cek apakah bot masih jalan:
```bash
# Cek process
ps aux | grep run_fair_value | grep -v grep

# Atau pakai PID yang disimpan
kill -0 $(cat bot.pid) 2>/dev/null && echo "✅ Running" || echo "❌ Stopped"
```

### Baca output terbaru:
```bash
# 50 baris terakhir
tail -50 bot_output.log

# Follow realtime
tail -f bot_output.log
```

### Hitung statistik dari log:
```bash
# Jumlah WIN
grep -c "WIN ✅" bot_output.log

# Jumlah LOSE
grep -c "LOSE ❌" bot_output.log

# Jumlah SKIP
grep -c "SKIP" bot_output.log

# Trades terakhir
grep "TRADE #" bot_output.log | tail -10

# Hourly reports
grep "HOURLY REPORT" bot_output.log | tail -5
```

### Buat ringkasan untuk user:
Kalau user minta "cek hasilnya", jalankan commands di atas lalu reporting format:
```
📊 STATUS BOT
  Status: ✅ Running / ❌ Stopped
  Uptime: X jam
  Trades: XX total (YY win / ZZ loss)
  Win Rate: XX.X%
  Balance: $XX.XX
  P&L: +/-$X.XX
  Last trade: [waktu]
```

---

## PERAN 3: RESTART & RECOVERY

### Kalau bot crash/stop:
```bash
# 1. Cek error
tail -20 bot_output.log

# 2. Kill old process (kalau masih ada)
kill $(cat bot.pid) 2>/dev/null

# 3. Restart
source .env
nohup python scripts/run_fair_value.py > bot_output.log 2>&1 &
echo $! > bot.pid
echo "Bot restarted with PID: $(cat bot.pid)"
```

### Kalau dependency error:
```bash
pip install -r requirements.txt
# lalu restart bot
```

### Kalau .env hilang/rusak:
```bash
cp .env.example .env
nano .env
# isi POLY_PRIVATE_KEY dan POLY_SAFE_ADDRESS
source .env
# lalu restart bot
```

---

## PERAN 4: DEBUGGING

### Kalau bot error, diagnosa:
```bash
# 1. Baca error terakhir
grep -i "error\|exception\|traceback" bot_output.log | tail -20

# 2. Cek koneksi
python scripts/test_connection.py

# 3. Test manual di Python
python -c "
from src.gamma_client import GammaClient
gamma = GammaClient()
info = gamma.get_market_info('BTC')
print('Market:', info['slug'] if info else 'No market')
print('Prices:', info['prices'] if info else 'N/A')
"
```

### Error umum & solusi:
| Error | Fix |
|-------|-----|
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| `POLY_PRIVATE_KEY required` | `source .env` |
| `No active market` | Tunggu 1-2 menit, market 15-min bergantian |
| `Order rejected` | Balance USDC kosong → deposit dulu |
| `Connection refused` | Internet/API down → bot auto-retry |
| `Binance 429` | Rate limit → kurangi lookback |

---

## PERAN 5: STRATEGY TUNING

### Setelah 100+ trades, analisis:
```bash
# Hitung win rate
WINS=$(grep -c "WIN ✅" bot_output.log)
LOSSES=$(grep -c "LOSE ❌" bot_output.log)
TOTAL=$((WINS + LOSSES))
WR=$(echo "scale=1; $WINS * 100 / $TOTAL" | bc)
echo "Win Rate: $WR% ($WINS/$TOTAL)"
```

### Keputusan berdasarkan data:

| Win Rate | Aksi |
|----------|------|
| > 65% selama 1 minggu | ✅ **Upgrade ke Phase 2** (compound 3%) |
| 55-65% | ✅ Lanjut Phase 1, kumpulkan data lagi |
| 50-55% | ⚠️ Naikkan threshold ke 0.03% |
| < 50% | 🛑 STOP. Review strategi. Beritahu user |

### Upgrade ke Phase 2 (compound):
```bash
# Stop bot lama
kill $(cat bot.pid)

# Cek balance terakhir dari log
grep "Balance:" bot_output.log | tail -1

# Start Phase 2 (contoh: balance sudah $25)
nohup python scripts/run_fair_value.py --balance 25 --phase2 --pct 3 > bot_output.log 2>&1 &
echo $! > bot.pid
```

### Ubah parameter tanpa edit kode:
```bash
# Lebih banyak trade:
python scripts/run_fair_value.py --threshold 0.01 --edge 0.003

# Lebih sedikit trade (safer):
python scripts/run_fair_value.py --threshold 0.05 --edge 0.01

# Hanya BTC + ETH:
python scripts/run_fair_value.py --coins BTC ETH

# Bigger size:
python scripts/run_fair_value.py --size 2.00

# Daily loss lebih longgar:
python scripts/run_fair_value.py --max-daily-loss 5.00
```

---

## PERAN 6: WATCHDOG (AUTO-RESTART)

Buat script yang auto-restart bot kalau crash:
```bash
cat > /root/watchdog.sh << 'EOF'
#!/bin/bash
while true; do
    if ! kill -0 $(cat /root/polymarket-trading-bot/bot.pid) 2>/dev/null; then
        echo "[$(date)] Bot stopped — restarting..."
        cd /root/polymarket-trading-bot
        source .env
        nohup python scripts/run_fair_value.py > bot_output.log 2>&1 &
        echo $! > bot.pid
        echo "[$(date)] Bot restarted with PID: $(cat bot.pid)"
    fi
    sleep 60
done
EOF

chmod +x /root/watchdog.sh
nohup /root/watchdog.sh > /root/watchdog.log 2>&1 &
```

---

## PERAN 7: TELEGRAM NOTIFIKASI (OPSIONAL)

Kalau user minta notif ke Telegram:
```python
# Tambahkan di fair_value.py atau buat script terpisah
import requests

TELEGRAM_BOT_TOKEN = "xxx"
TELEGRAM_CHAT_ID = "xxx"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

# Panggil di hourly_report():
send_telegram(f"📊 Hourly: {wins}W/{losses}L | WR: {wr}% | Balance: ${balance}")
```

---

## JADWAL AGENT

| Kapan | Apa yang dilakukan |
|-------|--------------------|
| **Setup awal** | Install, .env, test, launch bot |
| **Tiap 6 jam** | Cek bot masih jalan, baca log |
| **Tiap 24 jam** | Hitung WR, buat ringkasan untuk user |
| **Tiap 7 hari** | Evaluasi: upgrade Phase 2? Ubah parameter? |
| **Kalau crash** | Diagnosa error, fix, restart |
| **Kalau user minta** | Apapun yang diminta terkait bot |

---

## CODE REFERENCE (RINGKAS)

### File penting:
| File | Fungsi |
|------|--------|
| `strategies/fair_value.py` | Strategi utama (JANGAN UBAH kecuali tuning) |
| `scripts/run_fair_value.py` | Runner (CLI args) |
| `scripts/test_connection.py` | Cek koneksi |
| `src/bot.py` | TradingBot class |
| `src/gamma_client.py` | Market discovery |
| `.env` | Credentials |

### API yang dipakai bot:
| API | URL | Butuh key? |
|-----|-----|-----------|
| Binance Klines | `api.binance.com/api/v3/klines` | Tidak |
| Gamma (market discovery) | `gamma-api.polymarket.com` | Tidak |
| CLOB (trading) | `clob.polymarket.com` | Ya (dari .env) |
| Relayer (gasless) | `relayer-v2.polymarket.com` | Opsional |
