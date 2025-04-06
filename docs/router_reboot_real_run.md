# Router Reboot Mode — Test Procedure (REAL_RUN)

**Last Updated**: April 2025

This document outlines how to test the `router_reboot` logic in **REAL_RUN mode**, simulating a router reboot and IP change. The test verifies:

- Correct IP monitoring functionality.
- Appropriate Telegram notifications with recovery options.
- Bot shutdown and resumption after IP changes.

---

## Prerequisites

- `DRY_RUN = False` in `config.py`.
- Telegram bot is connected and responsive.
- Real funds are at risk; use with caution (e.g., minimal balance for testing).

---

## Test Flow

### 1. Start the Bot

Run the bot:

```bash
python main.py
```

Wait for the startup message (e.g., "Bot started in REAL_RUN mode").

---

### 2. Enable Reboot Mode (Optional)

Send via Telegram:

```
/router_reboot
```

**Expected Output:**

```
🟢 Router reboot mode ENABLED for 30 minutes.
```

The console logs the expiration time (e.g., "Expires at 15:45 Bratislava").

---

### 3. Change Your External IP

Options:

- Restart your router (preferred).
- Switch to a VPN or mobile hotspot.
- Wait up to 30 minutes if **not in reboot mode** (IP checks every 30 min), or 1–3 minutes **in reboot mode**.

---

### 4. Force an IP Check

After the IP changes, send:

```
/forceipcheck
```

**Expected Output (if NOT in reboot mode):**

```
🛰 Forced IP Check Result
🌐 Current IP: [new_ip]
📡 Previous IP: [old_ip]
🕒 Time: 04 Apr 2025, 15:16 (Bratislava)
⚙️ Router Reboot Mode: Disabled (N/A)
⚠️ IP has changed!
🚫 Bot will stop after closing orders.
ℹ️ Update Binance API IP whitelist with `[new_ip]`, then use /resume_after_ip.
```

**Expected Output (if in reboot mode):**

```
🛰 Forced IP Check Result
🌐 Current IP: [new_ip]
📡 Previous IP: [old_ip]
🕒 Time: 04 Apr 2025, 15:16 (Bratislava)
⚙️ Router Reboot Mode: 🟢 ENABLED (27 min left, until 15:45 Bratislava)
⚠️ IP has changed! No action needed (reboot mode active).
```

---

### 5. Handle IP Change (If Not in Reboot Mode)

If the bot initiates a stop:

1. Update the Binance API IP whitelist with `[new_ip]` in your Binance account.
2. Resume trading by sending:

```
/resume_after_ip
```

**Expected Output:**

```
✅ Bot resumed after IP change verification.
```

---

### 6. Cancel Pending Stop (If Needed)

If stopping is unwanted and positions are still open, you can cancel:

```
/cancel_stop
```

**Expected Output:**

```
✅ Stop process cancelled. Bot will continue running.
```

---

### 7. Review Logs

Check `telegram_log.txt` or console for:

- `Fetched current IP: [new_ip]`
- `✅ [telegram_utils] Message sent successfully`
- Ensure no errors (e.g., `Telegram response 400`)

---

### 8. Cancel Reboot Mode (Optional)

If reboot mode is still active and you'd like to exit early:

```
/cancel_reboot
```

**Expected Output:**

```
🔵 Router reboot mode CANCELLED.
Reboot mode deactivated early. IP monitoring returned to strict mode.
```

---

## Warnings

- **REAL_RUN Risk**: Real funds are involved. Use low balance for testing.
- **Network Stability**: Ensure router reboot doesn’t fully break connectivity.
- **Binance IP Whitelist**: Must be updated manually to resume bot after external IP change.

---

## Related Commands

| Command            | Description                                |
| ------------------ | ------------------------------------------ |
| `/router_reboot`   | Enable 30-min IP monitoring                |
| `/cancel_reboot`   | Disable reboot mode manually               |
| `/ipstatus`        | Show current/previous IP, reboot mode info |
| `/forceipcheck`    | Force IP check and report result           |
| `/resume_after_ip` | Resume bot after verifying updated IP      |
| `/cancel_stop`     | Cancel pending stop process                |

---

## Notes

- In `REAL_RUN`, an **unplanned IP change outside reboot mode** stops the bot after closing positions.
- To resume: update Binance IP whitelist → send `/resume_after_ip`.
- To prevent stop: act quickly and send `/cancel_stop` before positions close.
- In reboot mode, IP changes are safe and do not stop the bot.

See `ip_monitor.py` for implementation details.
