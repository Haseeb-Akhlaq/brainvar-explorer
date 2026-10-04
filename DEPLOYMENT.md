# Deployment — EC2, Docker Compose, Let's Encrypt

Single EC2 host running five containers: PostgreSQL, Django under gunicorn, the
built React app, an nginx reverse proxy terminating TLS, and certbot for
renewals. No RDS — the database is a container with a named volume.

```
                    ┌──────────────── EC2 ────────────────┐
   :443 ──────────► │ nginx  ──► frontend  (React build)  │
                    │        ──► backend   (gunicorn)     │
                    │              └──► db (postgres:16)  │
                    │            certbot (renews certs)   │
                    └─────────────────────────────────────┘

   brainvar.haseebakhlaq.com      -> frontend
   api.brainvar.haseebakhlaq.com  -> backend
```

Only nginx binds host ports. Postgres and Django are reachable only on the
internal Docker network.

---

## 1. DNS

Two A records at DreamHost, both pointing at the EC2 public IP:

| record | type | value |
|---|---|---|
| `brainvar.haseebakhlaq.com` | A | *elastic IP* |
| `api.brainvar.haseebakhlaq.com` | A | *elastic IP* |

Use an **Elastic IP**, or the address changes on every stop/start and the
certificate stops matching.

Confirm propagation before continuing — certbot fails otherwise:

```bash
dig +short brainvar.haseebakhlaq.com
dig +short api.brainvar.haseebakhlaq.com
```

## 2. EC2 instance

- **t3.small or larger.** t3.micro (1 GB) is tight: the loader holds a batch of
  gene rows while Postgres is also running.
- **20 GB storage** — the database is about 140 MB, the images a few hundred.
- **Security group inbound:** 22 (your IP only), 80, 443. Nothing else — the
  database must not be exposed.

Install Docker:

```bash
sudo dnf install -y docker git            # Amazon Linux 2023
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user          # log out and back in
sudo dnf install -y docker-compose-plugin
```

## 3. Code and configuration

```bash
git clone <repo> ~/brainvar && cd ~/brainvar

cp .env.prod.example .env.prod
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # POSTGRES_PASSWORD
nano .env.prod
```

`token_urlsafe` is used rather than Django's `get_random_secret_key()` because
the latter can emit `$`, which docker compose reads as a variable reference and
silently truncates.

## 4. Certificate

```bash
./init-letsencrypt.sh
```

One SAN certificate covering both hostnames. The script plants a self-signed
placeholder so nginx can start, requests the real certificate over the ACME
webroot challenge, then reloads.

Test the flow first without burning rate limit:

```bash
STAGING=1 ./init-letsencrypt.sh
```

Renewal is automatic: the certbot container attempts it twice daily and nginx
reloads every six hours.

## 5. Start

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

Migrations and `collectstatic` run automatically in the backend entrypoint,
which waits for Postgres to accept connections first.

## 6. Load the data

The raw files are not in git — 98 MB, and they are data rather than source. Copy
them up, then run the loader:

```bash
# from your laptop
scp -r data/brainvar ec2-user@<ip>:~/brainvar/data/

# on the server (~20 s)
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec backend python manage.py load_brainvar
```

Expected output: 176 samples, 60,155 genes, 121,953 aliases.

## 7. Admin user

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec backend python manage.py createsuperuser
```

Email and password only — there is no username field.

## 8. Verify

```bash
curl https://api.brainvar.haseebakhlaq.com/api/health/
curl -s https://api.brainvar.haseebakhlaq.com/api/genes/SCN2A/ | head -c 200
open https://brainvar.haseebakhlaq.com
```

Admin lives at `https://api.brainvar.haseebakhlaq.com/admin/`.

---

## Updating

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

The frontend bakes `VITE_API_URL` in at build time, so changing it requires a
rebuild, not just a restart.

## Things that will catch you out

**The Postgres password is fixed at first init.** `POSTGRES_PASSWORD` is only
applied when the volume is empty. Changing it later has no effect until the
volume is destroyed — which is exactly what happened during local testing, when
the dev and production stacks shared a volume. They now use separate compose
project names (`brainvar-local`, `brainvar-prod`) so it cannot recur.

**`SECURE_SSL_REDIRECT` must stay `False`.** nginx already terminates TLS and
redirects HTTP. Setting it True as well makes Django redirect a request that
arrived over HTTPS, producing a loop.

**Cookies are cross-site.** The app and the API are different origins, so the
session cookie needs `SameSite=None; Secure` and a `.brainvar.haseebakhlaq.com`
domain. Both are set in `.env.prod`. If login ever silently fails in Safari,
this is the first thing to check.

**The health check sends a Host header.** `ALLOWED_HOSTS` does not include
`127.0.0.1`, so the container probe passes
`-H 'Host: api.brainvar.haseebakhlaq.com'` rather than the list being widened.

## Backups

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec -T db pg_dump -U brainvar brainvar_explorer | gzip > backup-$(date +%F).sql.gz
```

The database is fully derivable from the three source files by re-running the
loader, so this is convenience rather than a hard requirement.
