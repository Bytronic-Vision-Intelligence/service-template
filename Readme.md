**Bytronic microservice Template**

Purpose: A minimal Python worker template to jumpstart microservice projects.

**Prerequisites**:
- Python 3.8 or newer
- pip

**Quick Start**:
1. Clone the repository.
2. Create and activate a virtual environment (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Edit configuration at `app/dependencies/config.yaml` as needed.
4. Run tests:

```powershell
python -m pytest test
```

**Configuration**:
- Main config: `app/dependencies/config.yaml`.
- Use the loader in `app/dependencies/loadConfig.py` to read settings from code.

**Project layout**:
- `app/` — application code and dependencies
- `docs/` — documentation and license
- `test/` — tests and examples
- `tools/` — helper scripts

**Notes**:
- See `app/readme.md` for app-specific instructions.
- License: see `docs/LISENCE`.

