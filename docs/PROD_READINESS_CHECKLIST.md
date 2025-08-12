# Production Readiness Checklist (v2.3)

## Must
- [ ] Version banner/log reflects v2.3 (or newer) in `main.py`.
- [ ] `ENABLE_WEBSOCKET` flag tested OFF/ON; keepalive resumes on listenKey invalidation.
- [ ] No `bare except:` in runtime modules. All exceptions logged with context.
- [ ] Runtime vs dev dependencies split (`requirements.txt` vs `requirements-dev.txt`).
- [ ] RiskGuard enabled with conservative limits for first week.
- [ ] Emergency shutdown closes positions and cancels orders; audit logger flushes/syncs.

## First Week Production
- [ ] Start with **$500–1000** max capital
- [ ] Max **2** concurrent positions
- [ ] Daily loss limit: **5%**
- [ ] Manual monitoring every **2–4 h**
- [ ] Detailed trade journal

## Performance Metrics
- [ ] Win rate **> 55%**, Max DD **< 15%**, Profit factor **> 1.5**
- [ ] **Every trade has SL**

## Nice to have
- [ ] Legacy isolated under `archive/` with README (not in .gitignore).
- [ ] Dev utilities under `tools/` and excluded from prod image.
- [ ] Logs rotate and are colorized in console.

## Validation
- [ ] `pytest -q` green.
- [ ] Dry-run on Binance Testnet: 1–2 cycles, 0 errors.
- [ ] Short smoke in prod with minimal size & limits; Telegram monitor receives alerts.

## Critical Pre-Production
- [ ] API keys have correct permissions (Futures enabled)
- [ ] Test emergency shutdown **with open positions**
- [ ] Verify TP/SL orders are placed and updated correctly
- [ ] Check **minimum position sizes** for all traded symbols
- [ ] Telegram alerts working (send a real test alert)

## First Week Production
- [ ] Start with **$500–1000** max capital
- [ ] Max **2 concurrent positions**
- [ ] Daily loss limit: **5%**
- [ ] Manual monitoring every **2–4 hours**
- [ ] Keep a detailed **trade journal**

## Performance Metrics
- [ ] Win rate **> 55%**
- [ ] Max drawdown **< 15%**
- [ ] Profit factor **> 1.5**
- [ ] **Every trade has SL** in place
