# Native backtesting performance

Mercury profiles before optimizing. The Python engine is the correctness oracle;
the optional C++ backend accelerates only the deterministic long-only execution
loop. Strategy construction, persistence, campaigns, agents, and reporting stay
in Python.

## Boundary and correctness

`PythonBacktestEngine` and `CppBacktestEngine` share the same point-in-time-safe
moving-average signal frame. The C++ binding accepts one-dimensional contiguous
`float64` open, close, and position arrays and returns numeric arrays for the
equity/accounting curves. Sparse trades are returned as records with an index,
which Python maps back to timestamps. Invalid shapes, NaNs, non-positive prices,
and negative costs raise `ValueError` rather than crashing a worker.

The signal remains shifted one bar before either engine sees it: the current
bar's open executes a decision formed from prior information. Python/C++ parity
tests compare equity, trades, costs, PnL, and metrics with floating-point
tolerances.

## Selecting an engine

Set `BACKTEST_ENGINE=cpp` for a worker or API process after the native extension
has been built. The default is `python`. Each persisted experiment records the
engine name and version under `run_metadata.backtest_engine`.

## Methodology

Run the exact same synthetic minute-bar data and moving-average parameters with
a warm-up excluded from timing:

```bash
python scripts/build_native.py
python scripts/benchmark_backtest.py --rows 100000 1000000 --repeats 5 \
  --output results/benchmarks/latest.json
```

The script reports median/minimum wall time, throughput, trade count, and ending
equity for every requested engine. It intentionally writes only explicitly
requested output files; `results/benchmarks/` is ignored so machine-specific
measurements never masquerade as portable source facts. Use the same file for a
Python-vs-C++ comparison and retain unfavorable or neutral cases.

Memory and worker scaling are not claimed from this unit benchmark. Measure them
separately with the actual worker topology, data source, and database because
serialization, PostgreSQL, and queue leases can become the next bottleneck.
