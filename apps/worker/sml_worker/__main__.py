"""CLI: python -m sml_worker --queues sml.model.effort-deepfake,sml.model.skku-r --gpu 1

Presets: --all (every queue; used with the simulated adapter in development).
One process handles one task at a time (GPU models are not shared across tasks).
"""

from __future__ import annotations

import argparse
import logging
import os

from .registry import queue_names


def main() -> None:
    parser = argparse.ArgumentParser(prog="sml_worker")
    parser.add_argument("--queues", default="", help="Comma-separated queue names (e.g. sml.model.qad)")
    parser.add_argument("--models", default="", help="Comma-separated model ids (expands to sml.model.<id>)")
    parser.add_argument("--all", action="store_true", help="Consume every model/audit/agent queue")
    parser.add_argument("--gpu", default="", help="GPU index for CUDA_VISIBLE_DEVICES")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--name", default="")
    parser.add_argument("--loglevel", default="INFO")
    args = parser.parse_args()

    queues = [q.strip() for q in args.queues.split(",") if q.strip()]
    queues += [f"sml.model.{m.strip()}" for m in args.models.split(",") if m.strip()]
    if args.all:
        queues = queue_names()
    if not queues:
        parser.error("Choose --queues, --models or --all")
    if args.gpu != "":
        os.environ["SML_WORKER_GPU"] = args.gpu
    logging.basicConfig(level=args.loglevel, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    from .app import app
    from .heartbeat import Heartbeat

    beat = Heartbeat(queues, args.gpu)
    beat.start()
    name = args.name or f"sml-worker-gpu{args.gpu or 'x'}-{os.getpid()}@%h"
    try:
        app.worker_main([
            "worker", "-Q", ",".join(queues), "-n", name, f"--concurrency={args.concurrency}", "--pool=prefork",
            f"--loglevel={args.loglevel}", "--without-gossip", "--without-mingle", "-O", "fair",
        ])
    finally:
        beat.stop()


if __name__ == "__main__":
    main()
