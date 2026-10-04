---
title: Troubleshooting
description: Problems hit during the first deployment, and their causes.
order: 2
---

Every item here was encountered on a clean Amazon Linux 2023 instance.

## `compose build requires buildx 0.17.0 or later`

AL2023's repositories have no `docker-buildx-plugin`. Install it directly:

```bash
BUILDX_VER=$(curl -sI https://github.com/docker/buildx/releases/latest \
  | grep -i '^location:' | sed 's|.*/tag/||' | tr -d '\r\n')

sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL "https://github.com/docker/buildx/releases/download/${BUILDX_VER}/buildx-${BUILDX_VER}.linux-amd64" \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
```

## `permission denied` when copying data to the server

Docker creates a missing bind-mount source directory **as root**, so `ec2-user`
cannot write into `data/` after the first `up`:

```bash
sudo chown -R ec2-user:ec2-user ~/brainvar-explorer/data
```

## `PermissionError: /data/brainVar.CPM-10042019.tsv`

The backend container runs as a non-root user by design. Files copied from macOS
often arrive as `drwx------`, which that user cannot read:

```bash
chmod -R a+rX ~/brainvar-explorer/data
```

The capital `X` adds execute on directories only, so data files do not become
executable. The mount is read-only, so the container still cannot modify
anything.

## The backend container is `unhealthy` but the API works

The health check must send a `Host` header Django accepts. `ALLOWED_HOSTS` does
not include `127.0.0.1`, so a bare probe returns `400`:

```yaml
test: ["CMD-SHELL", "curl -fs -H 'Host: api.brainvar.haseebakhlaq.com' http://127.0.0.1:8000/api/health/ || exit 1"]
```

Widening `ALLOWED_HOSTS` would also work, and is the worse fix.

## `password authentication failed` after changing the password

PostgreSQL applies `POSTGRES_PASSWORD` **only when it initialises an empty
volume**. Changing it later has no effect until the volume is destroyed.

This surfaced when the local and production stacks shared a volume, because they
shared a compose project name. They now use `brainvar-local` and `brainvar-prod`, so
it cannot recur.

## DNS records that never resolve

Records added at a provider that is not authoritative for the domain do nothing.
Check who actually answers:

```bash
dig +short NS haseebakhlaq.com
```

For this domain the answer is `nsone.net` — Netlify DNS — so records belong in
Netlify, not in the registrar's panel.

## `SECURE_SSL_REDIRECT` causes a redirect loop

nginx terminates TLS and already redirects HTTP. If Django also redirects, a
request that arrived over HTTPS is redirected again. Leave it `False` in
production and let nginx handle it; `SECURE_PROXY_SSL_HEADER` tells Django the
original request was secure.
