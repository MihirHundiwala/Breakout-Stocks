# Limitations and honest claims

- The system is designed and tested for a personal NSE watchlist, not a full
  exchange-wide real-time scanner.
- Analysis is end-of-day. It does not stream quotes or place trades. Telegram
  messages report changes in stored research classifications and are not entry,
  exit, target, stop-loss, or investment recommendations.
- The technical rules are explainable and historically measurable, but still
  need broader calibration across regimes before any predictive claim.
- The historical report avoids look-ahead bias, but a present-day selected
  watchlist has survivorship and selection bias. It is not a point-in-time NSE
  universe backtest.
- `technical-v19` requires a complete date-aligned Nifty 500 relative-strength
  window. Missing benchmark coverage produces `NO_SETUP` with an explicit
  reason; it is never treated as weak or zero. Historical `technical-v4` results
  remain readable and could run without a complete Nifty 500 series. In that case
  relative strength is explicitly unknown and its score weight is redistributed;
  it is never treated as zero or described as a market-wide percentile.
- Weekly long-base bars are derived from stored daily OHLCV and are not an
  independent provider series. This avoids extra API calls and inconsistent
  histories, but weekly thresholds still require broader out-of-sample
  calibration before predictive claims.
- Fundamentals display source coverage and stored statement/ratio data; the
  planned richer sector-specific derived engine remains deliberately limited.
- Missing fundamentals are unknown. They are not converted into zero, a failed
  rule, or a favorable valuation.
- The app does not detect or repair corporate actions. The administrator must
  identify an affected stock, globally delete it, and add it again. This removes
  prior memberships and research history and does not independently prove that
  the provider's replacement history is correctly adjusted.
- Provider availability, corrections, suspensions, and rate limits can delay a
  result. Incomplete candle history never produces a new signal.
- The Upstox Analytics Token requires annual rotation. The application does not
  implement OAuth or handle brokerage account credentials.
- The GitHub weekday schedule is economical, not highly available. Durable
  database state allows a safe manual research rerun after an outage. GitHub may
  start a scheduled workflow later than its nominal time under platform load.
  The 8:30 AM Telegram digest is deliberately best-effort and non-durable, so a
  missed or failed run is not delivered later.
- Render/Vercel/Neon configuration is prepared but deployment and current free-
  tier behavior must be verified at the time of publishing.
- There is one administrator. Multi-user authorization, audit administration,
  password reset, and account recovery are outside V1.
- Document upload, OCR, embeddings, company Q&A, and AI research are deferred.
