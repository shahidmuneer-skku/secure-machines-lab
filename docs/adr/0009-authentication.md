# 0009 · Sessions for browsers, API keys for machines, MFA for staff

**Context.** The brief asks for standard security protocols for login and role management; the
same API serves the web app and programmatic clients.

**Decision.** Browsers use server-side sessions via django-allauth's headless API (HttpOnly,
Secure, `__Host-` cookies; CSRF protection; idle, absolute and remember-me timeouts) rather than
JWTs in browser storage. Machines use API keys (hashed with a server pepper, scoped, optionally
IP- and model-restricted, rate-limited, expiring). Passwords use Argon2id and a breached-password
check; second factors are TOTP, recovery codes and passkeys. Roles are Django groups with
capability permissions defined in `config/roles.yaml`; every staff role requires a session that
passed two-factor authentication, and the Django data admin is limited to such superuser
sessions.

**Consequences.** Sessions can be listed and revoked individually and are invalidated on password
reset. API keys never grant access to account, key-management or admin endpoints. Staff must
enrol a second factor before the admin console opens.
