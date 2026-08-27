# Tests

Pytest, covering config resolution, the MQTT subscriber helpers, and the main
loop. No broker is required: `fakes.py` supplies stand-ins for the client,
config, and threads.

```bash
python -m pytest test
```

`pytest.ini` sets `pythonpath = . app`, so tests import exactly the way the
runtime does (`from main import ...`, `from dependencies.loadConfig import ...`)
while the `app.dependencies....` style used by other Bytronic services also
resolves.

`conftest.py` holds one autouse fixture pinning `sys.argv` to `--test`.
Without it every config call would raise `SystemExit`, because `loadConfig`
reads `sys.argv` and pytest's own arguments are what it would otherwise find.
Tests that need a different config override `sys.argv` themselves.

Name test files `test_*.py`, lowercase. Pytest's default collection pattern
will not pick up `Test_*.py` on a case-sensitive filesystem, which is easy to
miss on macOS and Windows.
