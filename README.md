# Holehe GUI

A native desktop application built with **PyQt6** that wraps the
[`holehe`](https://github.com/megadose/holehe) OSINT library.

## Features

- Asynchronous checks of ~120 sites without blocking the UI.
- Live‑updating results table.
- Start / Stop control.
- Export results to CSV or JSON.
- Dark‑mode toggle.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
