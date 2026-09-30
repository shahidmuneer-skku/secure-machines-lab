"""CLI for model workers.

    python -m sml_worker --detectors --gpu 0 --concurrency 4   # detectors on one GPU
    python -m sml_worker --agents --concurrency 2               # news / explain-why agents (Ollama)
    python -m sml_worker --models skku-p2 --gpu 3               # a worker dedicated to one model

Detector tasks start only when their GPU memory fits (sml_worker/gpu.py), so concurrency is an
upper bound, not a promise: tasks that do not fit wait while the others run. Agent runs share one
loaded LLM (sml_worker/agents/ollama.py). --all consumes everything (development).
"""

from __future__ import annotations

import argparse
import logging
import os

from .registry import AGENT_QUEUES, detector_queues, queue_names


def main() -> None:
    parser = argparse.ArgumentParser(prog="sml_worker")
    parser.add_argument("--queues", default="", help="Comma-separated queue names (e.g. sml.model.qad)")
    parser.add_argument("--models", default="", help="Comma-separated model ids (expands to sml.model.<id>)")
    parser.add_argument("--all", action="store_true", help="Consume every model/audit/agent queue")
    parser.add_argument("--detectors", action="store_true", help="Consume every model/audit/long-video queue")
    parser.add_argument("--agents", action="store_true", help="Consume the news and explain-why agent queues")
    parser.add_argument("--gpu", default="", help="GPU index for CUDA_VISIBLE_DEVICES")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--name", default="")
    parser.add_argument("--loglevel", default="INFO")
    args = parser.parse_args()

    queues = [q.strip() for q in args.queues.split(",") if q.strip()]
    queues += [f"sml.model.{m.strip()}" for m in args.models.split(",") if m.strip()]
    if args.all:
        queues = queue_names()
    else:
        if args.detectors:
            queues += detector_queues()
        if args.agents:
            queues += AGENT_QUEUES
    if not queues:
        parser.error("Choose --detectors, --agents, --queues, --models or --all")
    if args.gpu != "":
        os.environ["SML_WORKER_GPU"] = args.gpu
    logging.basicConfig(level=args.loglevel, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    from .app import app
    from .heartbeat import Heartbeat

    beat = Heartbeat(queues, args.gpu)
    beat.start()
    role = "agents" if args.agents and not args.detectors else f"gpu{args.gpu or 'x'}"
    name = args.name or f"sml-worker-{role}-{os.getpid()}@%h"
    try:
        app.worker_main([
            "worker", "-Q", ",".join(queues), "-n", name, f"--concurrency={args.concurrency}", "--pool=prefork",
            f"--loglevel={args.loglevel}", "--without-gossip", "--without-mingle", "-O", "fair",
        ])
    finally:
        beat.stop()


if __name__ == "__main__":
    main()
