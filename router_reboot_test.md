# 🧪 Router Reboot Mode — Test Procedure (Dry Run)

This document describes how to safely test the `router_reboot` logic in **DRY_RUN mode**, simulating a real router reboot and IP change. The test helps ensure that:

- IP monitoring works correctly
- Telegram messages are triggered appropriately
- The bot does **not stop** if the IP changes during reboot mode

---

## ✅ Prerequisites
- `DRY_RUN = True` in `config.py`
- Telegram bot is connected and responsive
- No critical real funds involved

---

## 🔁 Test Flow

### 1. Start the bot
Launch the bot as usual (with `python main.py`). Wait for startup message.

### 2. Trigger reboot mode
Send the following command in Telegram:
```
/router_reboot
```
You should receive:
```
🟢 Router reboot mode ENABLED for 30 minutes.
```
Console will show expiration time.

### 3. Change your external IP
Options:
- Restart your router (recommended)
- Switch to VPN or mobile hotspot temporarily

Wait ~1–3 minutes (bot checks IP every 3 minutes).

### 4. Trigger manual check
Once the IP has changed, send:
```
/forceipcheck
```
Expected message:
```
⚠️ IP Address Changed!
✅ No action needed. IP changed while reboot mode is active (30 min safe window).
```

### 5. Review bot logs
- Confirm Telegram logs are correct
- Check log file or console

### 6. Register new IP in Binance (if needed)
If using real keys and Binance IP restrictions are enabled — add new IP manually.

### 7. Optional: cancel reboot mode early
If everything is OK, send:
```
/cancel_reboot
```
You’ll see:
```
🔵 Router reboot mode CANCELLED.
Reboot mode deactivated early. IP monitoring returned to strict mode.
```

---

## 🛑 Warnings
- Do not use real trading mode for this test.
- Ensure router reboot doesn’t disrupt your network entirely (or use mobile backup).

---

## 📦 Related commands
- `/router_reboot` — Enable reboot mode
- `/cancel_reboot` — Disable reboot mode manually
- `/ipstatus` — Show current/previous IP and reboot mode status
- `/forceipcheck` — Force IP check and show change result
