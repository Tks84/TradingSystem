# Northstar Trading Research

A GitHub Pages dashboard and staged research pipeline for the **HTF Trend Pullback Trail** price-action system.

## Current phase

This commit contains the phase-one dashboard scaffold and a committed EURUSD H1 sample CSV. It intentionally does **not** run a backtest or parameter optimization yet. The page shows `NOT RUN` rather than implying a result. The Python module entry points are present for the next implementation phase.

The chart is dependency-free and draws sample candles and EMA50 on a canvas. It loads `data/EURUSD_H1.csv` when served over HTTP and uses an embedded fallback when opened directly from disk. The other pair choices are UI placeholders until their sample files are added.

## Run locally

From the repository root:

```powershell
python -m http.server 8000
```

Open <http://localhost:8000/docs/>. Opening `docs/index.html` directly also works using its embedded EURUSD fallback.

**Note:** If `python` is not on your PATH, use `uv`:

```powershell
uv run python -m http.server 8000
```

The Python research dependencies are listed in `requirements.txt`:

```powershell
uv run pip install -r requirements.txt
```

Run the research entry points:

```powershell
uv run python -m src.backtest
uv run python -m src.optimize
uv run python -m src.build_site
```

These currently print a phase message, as the backtest and optimization are deferred. The strategy, indicators, costs, 70/30 split, small parameter grid, OOS gates, and robustness checks will be implemented in the next phase. Optimization must remain limited to the declared grid and must never tune against out-of-sample data.

## Publish with GitHub Pages

1. Push this repository to GitHub.
2. In **Settings > Pages**, choose **Deploy from a branch**.
3. Select the default branch and the `/docs` folder.
4. Save and open the generated Pages URL.

## Research rules

This is research software, not financial advice. Do not use it for live broker execution. TradingView free data and the committed dataset will not match tick-for-tick because of feed, aggregation, timezone, and historical revision differences.

Optimizing until a backtest target is hit is forbidden. If the eventual candidate fails the out-of-sample gates or robustness checks, the report and dashboard must say `FAILED` or `FRAGILE`; the grid must not be expanded and extra indicators must not be added to rescue the result.
