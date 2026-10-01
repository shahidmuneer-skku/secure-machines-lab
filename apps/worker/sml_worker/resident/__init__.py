"""Resident detector models: weights stay loaded on a GPU between tasks (owner, 2026-10-01).

`server.py` (run with the model's conda Python) keeps one script's model loaded and serves runs of
it; `hook/sitecustomize.py` redirects launches of that script to the server; `supervisor.py` starts
and watches the servers. A model whose server is not up loads per task, as before.
"""
