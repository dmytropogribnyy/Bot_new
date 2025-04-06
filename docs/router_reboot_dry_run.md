# Router Reboot Mode — Test Procedure (DRY_RUN)

**Last Updated**: April 2025

This document outlines how to test the `router_reboot` logic in **DRY_RUN mode**, simulating a router reboot and IP change. The test verifies:

- Correct IP monitoring functionality.
- Appropriate Telegram notifications.
- No bot shutdown during reboot mode IP changes.

---

## Prerequisites

- `DRY_RUN = True` in `config.py`.
- Telegram bot is connected and responsive.
- No real funds at risk (DRY_RUN ensures simulation).

---

## Test Flow

### 1. Start the Bot

Run the bot:

```bash
python main.py
```

Wait for the startup message (e.g., "Bot started in DRY_RUN mode").

### 2. Enable Reboot Mode

Send via Telegram:

```
/router_reboot
```

**Expected Output:**

```
🟢 Router reboot mode ENABLED for 30 minutes.
```

The console logs the expiration time (e.g., "Expires at 15:45 Bratislava").

### 3. Change Your External IP

Options:

- Restart your router (preferred).
- Switch to a VPN or mobile hotspot.
- Wait 1–3 minutes (IP checks occur every 3 minutes in reboot mode).

### 4. Force an IP Check

After the IP changes, send:

```
/forceipcheck
```

**Expected Output:**

```
🛰 Forced IP Check Result
🌐 Current IP: [new_ip]
📡 Previous IP: [old_ip]
🕒 Time: 04 Apr 2025, 15:16 (Bratislava)
⚙️ Router Reboot Mode: 🟢 ENABLED (27 min left, until 15:45 Bratislava)
✅ No changes detected OR ⚠️ IP has changed! No action needed (reboot mode active).
```

The bot continues running (no stop in reboot mode).

### 5. Review Logs

Check `telegram_log.txt` or the console for messages like:

- `Fetched current IP: [new_ip]`
- `✅ [telegram_utils] Message sent successfully`
- Ensure no errors (e.g., `Telegram response 400`)

### 6. Update Binance IP (If Applicable)

If using real API keys with IP restrictions, manually add the new IP to Binance (not required in DRY_RUN).

### 7. Cancel Reboot Mode (Optional)

To end early, send:

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

- **Avoid REAL_RUN**: In real mode, an unplanned IP change triggers `/stop`; test only in DRY_RUN.
- **Network Stability**: Ensure the router reboot doesn’t fully disrupt connectivity (use a mobile backup if needed).

---

## Related Commands

| Command          | Description                           |
| ---------------- | ------------------------------------- |
| `/router_reboot` | Enable 30-min IP monitoring           |
| `/cancel_reboot` | Disable reboot mode manually          |
| `/ipstatus`      | Show current/previous IP, mode status |
| `/forceipcheck`  | Force IP check and report result      |

---

## Notes

In `REAL_RUN`, an unplanned IP change stops the bot after closing positions, unlike `DRY_RUN`’s safe continuation.

Use `/resume_after_ip` (or a similar recovery command) in `REAL_RUN` to continue after updating the Binance API IP whitelist, or `/cancel_stop` to prevent stopping if acted upon quickly.

See `ip_monitor.py` for implementation details.
