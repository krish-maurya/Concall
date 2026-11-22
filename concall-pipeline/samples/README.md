# Samples
Real samples (raw transcript, JSON, Markdown for 3+ companies) must be generated on a machine with internet and an LLM key:

    # 1. add your key to .env, set LOOKBACK_DAYS=30 and WATCHLIST
    # 2. python run.py, then:
    curl -X POST "localhost:8000/api/backfill?days=30"
    # 3. export:
    python tools/export_samples.py

`example_output.json` is a SYNTHETIC illustration of the schema, not a real company's call.
