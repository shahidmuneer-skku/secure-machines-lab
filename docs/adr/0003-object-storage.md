# 0003 · S3 API for media; SeaweedFS on the single host

**Context.** Uploads (up to 4 GB videos), thumbnails, model artifacts and reports need durable
storage reachable by the API, the workers and browsers. The MinIO images could not be pulled on
the build host.

**Decision.** All storage goes through the S3 API (boto3 / django-storages): private bucket,
short-lived presigned URLs for downloads, and presigned multipart uploads straight from the
browser for videos over 200 MB. On the single host the S3 endpoint is SeaweedFS in Docker
Compose.

**Consequences.** Moving to AWS S3, Cloudflare R2 or MinIO is a configuration change
(`S3_ENDPOINT_URL`, `S3_PUBLIC_ENDPOINT_URL`, credentials). Large uploads never pass through
Django. The public endpoint must be served under its own host name with the Host header
preserved, because presigned URLs are signed for it (see `deploy/nginx/sml.conf`).
