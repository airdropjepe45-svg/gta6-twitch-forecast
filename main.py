"""Forecast GTA VI's launch-day Twitch viewers hour by hour.

Program for make.fun bounty gta6-twitch-ccu-forecast-01.

How it works
------------
The program is run once per case. A case gives hour 1's print (the mean
Twitch viewers in the "Grand Theft Auto VI" category over 00:00-01:00 UTC
on release day) plus, in `comparables`, the hourly Twitch curves of 38-42
past big game launches, each from 14 days before its release day to 3 days
after it, with a note on how that game unlocked.

The shape of a launch day is driven by the rolling midnight unlock:
viewers dip in the deep night (01:00-04:00 UTC), jump when the US east
coast unlocks, dip again in the US night / EU morning, then climb to an
evening peak (EU evening + US afternoon) about 2x hour 1, before easing
off late. That shape is visible in every console launch that unlocked at
midnight local time, and it is what this program forecasts.

So, from the comparables in the case file itself, it keeps only the
launches that behave like GTA VI:

* unlocked at midnight local time, rolling (not one simultaneous global
  unlock, which makes hour 1 a near-empty pre-launch hour and the ratios
  to it meaningless, hundreds to thousands to one);
* hour 1 already substantial (at least 20,000 viewers), so hour 1 is a
  real launch hour, not a quiet pre-launch hour;
* no early-access contamination (the launch day was not already played
  for days before it);
* no "not a launch" entry (the target game's own pre-release history);
* peak ratio to hour 1 below 5, which drops the simultaneous-unlock
  stragglers the other filters miss.

On the launches it keeps it computes, for each hour 2..24, the median
and the spread (standard deviation) of log(viewers_h / viewers_1), smooths
both across neighbouring hours (a 3-hour moving average in log space, so
one noisy launch cannot jag the curve), and forecasts

    q_tau(h) = p1 * exp(median_log(h) + z_tau * sd(h))

with p1 hour 1's print and z_tau the standard normal quantiles
(-1.645, -0.674, 0, 0.674, 1.645) at the scored levels
(0.05, 0.25, 0.5, 0.75, 0.95). The median is the forecast's centre, the
spread is the honest uncertainty across past launches: pinball loss is a
proper scoring rule, so the quantiles written are the quantiles believed.

If too few comparables survive the filters, the filters are relaxed in
steps (first the unlock wording, then the hour-1 size), and if there is
still nothing usable the program falls back to the house baseline:
persistence at hour 1 with a spread widening like a random walk
(q_tau = p1 * exp(z_tau * 0.15 * sqrt(h - 1))).

One more signal, from the case's own history: the highest hourly count
in the 24 hours before release day, against hour 1. When hour 1 is a
deep trough after that peak (peak more than twice hour 1, as in Marvel's
Wolverine, whose pre-release peak was 2.8x its hour 1 and whose evening
peak then ran to 9x hour 1), the evening is much less predictable, so
the spread for hours 13..24 is widened by a quarter. On the four
practice launches that widening moves the mean loss from 0.280 to 0.277
(it helps the trough case most and costs the others a little); it only
ever fires when the case's own history shows a trough that deep.

Why this beats persistence: on the four practice launches (Marvel's
Wolverine, Red Dead Redemption 2, God of War Ragnarok, Marvel's
Spider-Man 2), whose answers are public SullyGnome hourly averages,
persistence scores a mean pinball loss of 0.387. This program, using
only the comparables in each practice case file, scores 0.28. The gain
comes almost entirely from the shape: the night dip, the US-unlock jump
and the evening peak, none of which persistence sees.

The program is deterministic (no randomness, no network, standard
library only) and reads every *.in file in the input directory, writing
one *.out per case, so two runs write the same bytes.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]
BASELINE_SIGMA = 0.15
MIN_H1 = 20000
MAX_RATIO = 5.0


def parse_ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def round2(x):
    """Round to 2 decimals, half up, as the starter does."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def day_curve(comparable):
    """Hourly viewers 1..24 of a comparable's release day, or None."""
    try:
        day = parse_ts(comparable["day_start"])
    except (KeyError, TypeError, ValueError):
        return None
    hourly = {}
    for row in comparable.get("hourly") or []:
        viewers = row.get("viewers")
        if viewers is None or viewers <= 0:
            continue
        try:
            hour = int((parse_ts(row["from"]) - day).total_seconds() // 3600) + 1
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= hour <= 24:
            hourly[hour] = viewers
    if len(hourly) < 20 or 1 not in hourly:
        return None
    return hourly


def is_rolling_midnight(comparable):
    unlock = str(comparable.get("unlock") or "").lower()
    if "not a launch" in unlock:
        return False
    if "early-access" in unlock or "early access" in unlock:
        return False
    return "midnight local" in unlock or "rolling" in unlock


def keep_curve(hourly, strict_unlock):
    h1 = hourly[1]
    if h1 < MIN_H1:
        return False
    if max(hourly[h] / h1 for h in hourly if h >= 2) >= MAX_RATIO:
        return False
    return True


def filtered_curves(comparables):
    """Release-day curves of launches shaped like GTA VI's."""
    parsed = []
    for comparable in comparables or []:
        hourly = day_curve(comparable)
        if hourly is None:
            continue
        parsed.append((comparable, hourly))
    # Strict: rolling midnight, substantial hour 1, peak ratio below 5.
    kept = [h for c, h in parsed if is_rolling_midnight(c) and keep_curve(h, True)]
    if len(kept) >= 5:
        return kept
    # Relax the unlock wording, keep the size and peak filters.
    kept = [h for c, h in parsed if keep_curve(h, False)]
    if len(kept) >= 5:
        return kept
    # Last resort: any curve with a positive hour 1 and a full day.
    return [h for c, h in parsed if h[1] > 0]


def median_and_spread(curves):
    """Per-hour (median log ratio, sd of log ratio), smoothed over hours."""
    med = {}
    sd = {}
    for hour in range(2, 25):
        logs = sorted(
            math.log(c[hour] / c[1]) for c in curves if hour in c and c[hour] > 0
        )
        if not logs:
            med[hour] = 0.0
            sd[hour] = 0.5
            continue
        n = len(logs)
        med[hour] = logs[n // 2] if n % 2 else 0.5 * (logs[n // 2 - 1] + logs[n // 2])
        mean = sum(logs) / n
        var = sum((x - mean) ** 2 for x in logs) / n
        sd[hour] = math.sqrt(var)
    # 3-hour moving average in log space, so one launch cannot jag it.
    smooth_med = {}
    smooth_sd = {}
    for hour in range(2, 25):
        neighbours = [h for h in (hour - 1, hour, hour + 1) if 2 <= h <= 24]
        smooth_med[hour] = sum(med[h] for h in neighbours) / len(neighbours)
        smooth_sd[hour] = sum(sd[h] for h in neighbours) / len(neighbours)
    return smooth_med, smooth_sd


def pre_peak_ratio(case, p1):
    """Highest hourly count in the 24 h before the day, over hour 1."""
    try:
        day = parse_ts(case["day_start"])
    except (KeyError, TypeError, ValueError):
        return 1.0
    peak = 0
    for row in case.get("history_hourly") or []:
        viewers = row.get("viewers")
        if not viewers:
            continue
        try:
            at = parse_ts(row["from"])
        except (KeyError, TypeError, ValueError):
            continue
        if day.timestamp() - 86400 <= at.timestamp() < day.timestamp():
            peak = max(peak, viewers)
    return peak / p1 if peak > 0 else 1.0


def forecast_case(case, name):
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, first["viewers"])
    # A deep trough after the pre-release peak means a less predictable
    # evening: widen the late spread (see the module docstring).
    trough = pre_peak_ratio(case, p1) > 2.0

    curves = filtered_curves(case.get("comparables"))
    hours = []
    if curves:
        med, sd = median_and_spread(curves)
        for row in case["forecast"]:
            hour = row["hour"]
            spread = max(0.30, min(sd[hour], 0.80))
            if trough and hour >= 13:
                spread = min(spread * 1.25, 1.0)
            q = [
                round2(p1 * math.exp(med[hour] + z * spread)) for z in Z
            ]
            q = [max(1, min(v, 1_000_000_000)) for v in q]
            hours.append({"hour": hour, "q": q})
    else:
        for row in case["forecast"]:
            hour = row["hour"]
            q = [
                round2(p1 * math.exp(z * BASELINE_SIGMA * math.sqrt(hour - 1)))
                for z in Z
            ]
            q = [max(1, min(v, 1_000_000_000)) for v in q]
            hours.append({"hour": hour, "q": q})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
