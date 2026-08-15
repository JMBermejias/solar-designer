#!/bin/sh
cd "$(dirname "$0")"
exec venv/bin/python solar_cli.py --host 127.0.0.1 --port 5000
