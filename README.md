# Bookivox SDKs

Official SDKs and CLI for the [Bookivox](https://bookivox.com) API: typed access
to agents, node types, tools, knowledge-base documents, recordings, credentials
and test calls.

| Package | Language | Install | Source |
| --- | --- | --- | --- |
| `bookivox` | Python 3.11+ | `pip install bookivox` | [`python/`](./python) |
| `@bookivox/sdk` | TypeScript (Node 18+) | `npm install @bookivox/sdk` | [`typescript/`](./typescript) |

The `bookivox` CLI ships inside the Python package: one install gives you both
the SDK and the command-line tool.

- **Typed**: models and method signatures generated from the API OpenAPI schema.
- **Safe by default**: timeouts, retries on idempotent verbs only, typed errors, no secret logging.
- **Fixed origin**: every request targets `https://api.bookivox.com` over TLS; the URL is not configurable.
- **Minimal dependencies**: `httpx` for Python, the global `fetch` for TypeScript.

## Quick start

```bash
pip install bookivox
export BOOKIVOX_API_KEY="bookeys_sk-..."
bookivox workflows list
```

```python
import os
from bookivox_sdk import Bookivox

with Bookivox(api_key=os.environ["BOOKIVOX_API_KEY"]) as client:
    for workflow in client.list_workflows():
        print(workflow["id"], workflow.get("name"))
```

```ts
import { Bookivox } from "@bookivox/sdk";

const client = new Bookivox({ apiKey: process.env.BOOKIVOX_API_KEY! });
const workflows = await client.listWorkflows();
```

Full documentation, including installation, authentication and error handling:
<https://docs.bookivox.com/sdk/overview>.

## Repository layout

```
generate_sdk.py     generator (stdlib only): OpenAPI -> both SDKs
generate_sdk.sh     wrapper: ./generate_sdk.sh [--check]
openapi.sdk.json    filtered public contract (x-sdk-method)
python/             Python SDK + CLI (hatchling, src layout)
typescript/         TypeScript SDK (ESM, tsc)
```

## Generated code

`python/src/bookivox_sdk/models.py`, `python/src/bookivox_sdk/_generated.py`,
`typescript/src/types.ts` and `typescript/src/generated.ts` are generated and
must never be edited by hand. Regenerate from the repository root:

```bash
./generate_sdk.sh                        # fetch the live schema
./generate_sdk.sh --spec ./openapi.json  # use a local schema file
./generate_sdk.sh --check                # CI: fail if generated files are stale
```

## Development

```bash
# Python
cd python && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest

# TypeScript
cd typescript && npm install
npm run typecheck && npm run build
```

## Releasing

CI runs on every push and pull request: generated files must be up to date,
the Python package is built and checked on 3.11–3.13, and the TypeScript SDK is
typechecked and built.

A release is a tagged commit. Bump the version in `python/pyproject.toml` and
`typescript/package.json`, then:

```bash
git tag -a v0.2.0 -m "Bookivox SDKs 0.2.0"
git push origin v0.2.0
```

The `Release` workflow verifies that the tag matches both versions, then
publishes to PyPI and npm using **trusted publishing (OIDC)**: no token is
stored in this repository. One-time setup: register the trusted publisher on
PyPI (`bookivox`) and npm (`@bookivox/sdk`) with workflow `release.yml`.

## Security

- Never commit `.env` files or API keys; load them from your platform's secret manager.
- Never ship an API key to a browser or mobile app: keep both SDKs on the server.
- `test_phone_call` / `testPhoneCall` triggers a **real, billable phone call**.

## License

MIT, see [LICENSE](./LICENSE).
