# The hosted table (P6.7c). Runs `dndc serve`, which since P6.7b-iii boots with nobody
# playing and waits for a browser to start an evening — the thing that made this image
# possible to write at all.
#
# **Installed editable into /app rather than as a wheel, and that is deliberate.**
# `config.yaml`, `.env` and `data/srd/` are resolved as `Path(__file__).parents[2]` from
# inside the package, so a normal site-packages install would put the code somewhere the
# data is not and every one of those lookups would land in the wrong place. Editable from
# /app makes the container's layout the same shape as the repo's, which means a path that
# works on Kelly's PC works here — and nothing has to learn a second way to find itself.
FROM python:3.12-slim

WORKDIR /app

# Dependencies first, so a change to the game does not reinstall FastAPI.
COPY pyproject.toml ./
COPY src/dndc/__init__.py src/dndc/__init__.py
RUN pip install --no-cache-dir -e ".[web]"

COPY src/ src/
COPY config.yaml ./
COPY data/ data/

# The normalized SRD is generated, never committed (OD-7) — a normalization bug must not
# be freezable into the repo. So it is built here, from the pinned raw data that *is*
# committed, and `verify` fails the build rather than shipping an image whose dataset
# does not match its pin.
RUN dndc srd ingest && dndc srd verify

# Campaign state is data, not code, and it lives on a volume (P6.7a gave it a path that
# is not "beside the code" precisely so this line could exist).
ENV DNDC_CAMPAIGNS_DIR=/data/campaigns
# A hosted table is one of the two exposures that make the token mandatory (P6.7b-i):
# with this set, an absent or short `DNDC_WEB_TOKEN` refuses to start rather than
# serving the campaign to whatever can reach the port.
# (BuildKit flags this as SecretsUsedInArgOrEnv because the name contains TOKEN.
# It is a boolean: 1 means "this exposure needs a key". The key itself arrives at
# runtime through env_file and never enters a layer.)
ENV DNDC_WEB_REQUIRE_TOKEN=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# `0.0.0.0` inside the container is the container's own namespace, not the host's — what
# is actually exposed is decided by the `ports:` line in docker-compose.yml, which binds
# 192.168.50.46 and not the tailnet. The token is required regardless, and by both
# routes: this is a wildcard bind *and* DNDC_WEB_REQUIRE_TOKEN is set.
CMD ["dndc", "serve", "--serve-host", "0.0.0.0", "--serve-port", "8080"]
