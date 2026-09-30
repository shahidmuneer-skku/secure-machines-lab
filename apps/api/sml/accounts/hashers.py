from django.contrib.auth.hashers import Argon2PasswordHasher


class StrongArgon2PasswordHasher(Argon2PasswordHasher):
    """Argon2id with 64 MiB memory (OWASP minimum is 19 MiB; spec asks for >= 64 MB)."""

    algorithm = "argon2"
    time_cost = 3
    memory_cost = 65536  # KiB
    parallelism = 4
