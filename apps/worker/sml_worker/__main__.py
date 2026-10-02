"""CLI for model workers.

    python -m sml_worker --detectors --gpu 0 --concurrency 4   # detectors on one GPU
    python -m sml_worker --agents --concurrency 2               # news / explain-why agents (Ollama)
    python -m sml_worker --models skku-p2 --gpu 3               # a worker dedicated to one model
    python -m sml_worker --resident                              # keep resident models (models.yaml) and the
                                                                 # image studio server (studio.yaml) loaded
    python -m sml_worker --studio --concurrency 2                # image studio jobs (run on the studio server)

Detector tasks start only when their GPU memory fits (sml_worker/gpu.py), so concurrency is an
upper bound, not a promise: tasks that do not fit wait while the others run. Agent runs share one
loaded LLM (sml_worker/agents/ollama.py). --all consumes everything (development).
"""

from __future__ import annotations

import argparse
import logging
import os

from .registry import AGENT_QUEUES, STUDIO_QUEUES, detector_queues, queue_names


def main() -> None:
    parser = argparse.ArgumentParser(prog="sml_worker")
    parser.add_argument("--queues", default="", help="Comma-separated queue names (e.g. sml.model.qad)")
    parser.add_argument("--models", default="", help="Comma-separated model ids (expands to sml.model.<id>)")
    parser.add_argument("--all", action="store_true", help="Consume every model/audit/agent queue")
    parser.add_argument("--detectors", action="store_true", help="Consume every model/audit/long-video queue")
    parser.add_argument("--agents", action="store_true", help="Consume the news and explain-why agent queues")
    parser.add_argument("--studio", action="store_true", help="Consume the image studio queue")
    parser.add_argument("--resident", action="store_true",
                        help="Start and watch the resident model servers (`resident` blocks in models.yaml); "
                             "--models limits it to those models")
    parser.add_argument("--gpu", default="", help="GPU index for CUDA_VISIBLE_DEVICES")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--name", default="")
    parser.add_argument("--loglevel", default="INFO")
    args = parser.parse_args()

    if args.resident:
        logging.basicConfig(level=args.loglevel, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        from .resident.supervisor import supervise

        supervise([m.strip() for m in args.models.split(",") if m.strip()] or None)
        return
    queues = [q.strip() for q in args.queues.split(",") if q.strip()]
    queues += [f"sml.model.{m.strip()}" for m in args.models.split(",") if m.strip()]
    if args.all:
        queues = queue_names()
    else:
        if args.detectors:
            queues += detector_queues()
        if args.agents:
            queues += AGENT_QUEUES
        if args.studio:
            queues += STUDIO_QUEUES
    if not queues:
        parser.error("Choose --detectors, --agents, --studio, --queues, --models or --all")
    if args.gpu != "":
        os.environ["SML_WORKER_GPU"] = args.gpu
    logging.basicConfig(level=args.loglevel, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    import faulthandler
    import signal

    from celery.signals import worker_ready

    from .app import app
    from .heartbeat import Heartbeat

    # `kill -USR2 <pid>` writes every thread's stack to the log (a frozen worker process can be read).
    faulthandler.register(signal.SIGUSR2, all_threads=True)
    beat = Heartbeat(queues, args.gpu)
    # The first beat runs here, before any thread exists: it imports and connects everything the
    # heartbeat uses. The thread starts only once Celery has forked its worker processes: a thread
    # busy (importing, connecting, running nvidia-smi) while the worker forks leaves its locks held in
    # the children, which then freeze on their first task (2026-10-02: 6 of 8 detector processes).
    beat.beat()
    worker_ready.connect(lambda **_: beat.start(), weak=False)
    role = ("agents" if args.agents and not args.detectors else "studio" if args.studio and not args.detectors
            else f"gpu{args.gpu or 'x'}")
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
