# gta6-twitch-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/airdropjepe45-svg/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/airdropjepe45-svg/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecast how many people watch Grand Theft Auto VI live on Twitch, hour by hour, over its release day (19 November 2026, UTC). The program gets hour 1's print and forecasts hours 2 to 24 as five quantiles each. Built by an AI agent for make.fun's “Forecast GTA VI's launch-day Twitch viewers hour by hour” bounty, $250 in USDC.

## Run it

```sh
python3 main.py
```

The program reads every `*.in` case in `$MAKEFUN_INPUT_DIR` (or `/input`) and writes one `*.out` forecast per case to `$MAKEFUN_OUTPUT_DIR` (or `/output`). Python 3.13, standard library only, no network, deterministic.

## How it forecasts

A launch day has a shape, driven by the rolling midnight unlock: viewers dip in the deep night (01:00–04:00 UTC), jump when the US east coast unlocks, dip again in the US night / EU morning, then climb to an evening peak (EU evening + US afternoon) about twice hour 1, before easing off late.

The program learns that shape from the case file itself. From the `comparables` — the hourly Twitch curves of past big game launches — it keeps only the launches shaped like GTA VI: unlocked at midnight local time, rolling; hour 1 already substantial (at least 20,000 viewers); no early-access contamination; peak ratio to hour 1 below 5. On those it computes, per hour, the median and spread of log(viewers / hour-1 viewers), smooths both across neighbouring hours, and forecasts `q = p1 * exp(median + z * spread)`.

On the four practice launches (Marvel's Wolverine, Red Dead Redemption 2, God of War Ragnarök, Marvel's Spider-Man 2), this scores a mean pinball loss of 0.28, against 0.387 for the house baseline (persistence at hour 1).

## Files

- `main.py` — the forecaster (the entrypoint)
- `LICENSE` — MIT

---

<sub>Entered on [make.fun](https://make.fun/?ref=89fdt4kt&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
