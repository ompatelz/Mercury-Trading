# Canonical End-to-End Research Mission

Mercury's canonical demo is an offline, deterministic, PAPER-only mission. It
uses seeded market bars so it does not require credentials, an external market
feed, or live trading access.

Run it with:

```bash
python -m pytest tests/integration/test_end_to_end_mission.py
```

The mission executes real Mercury components in order: campaign planning,
memory retrieval, deterministic hypothesis triage, durable worker jobs,
temporal validation, stress testing, portfolio ranking, champion selection,
PAPER-only shadow production simulation, governance records, and a persisted
campaign research artifact.

The assertion payload captures attempted experiments, rejected candidates,
runtime and cost-budget fields, risk flags, the selected champion, the shadow
simulation result, and the report artifact.  Synthetic inputs demonstrate
reproducibility only; they are not investment evidence or a live-trading run.
