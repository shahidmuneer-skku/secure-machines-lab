# 0008 · Django-free workers that run existing model scripts as subprocesses

**Context.** The detection models are research code with conflicting dependencies (different
PyTorch/CUDA versions per conda environment). They must not be retrained or rewritten, and a
crashing model must not take the platform down.

**Decision.** `apps/worker` is a small Celery application without Django. For each task it
downloads the input, runs the model's script with the Python of the model's conda environment
(argv from `config/models.yaml`, no shell), pins the GPU through the environment, parses the
score from stdout, uploads artifacts, and streams progress and log lines through Redis. Results
go back through a queue; the API owns all database writes. When an environment is missing the
worker can simulate results, and says so in the result.

**Consequences.** Models keep working exactly as their authors wrote them, and each runs in its
own process with a timeout and a clean kill. The cost is loading weights on every run; a warm
adapter type can be added for hot models without changing the contract.
