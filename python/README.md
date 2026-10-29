# Bookivox Python SDK

Official Python client **and CLI** for the [Bookivox](https://bookivox.com) API:
typed access to agents, node types, tools, knowledge-base documents, recordings,
credentials and test calls.

- **Typed**: generated `TypedDict` models and typed method signatures (`py.typed`).
- **Safe by default**: timeouts, retries on idempotent verbs only, typed errors, no secret logging.
- **One install**: `pip install bookivox` gives you both the SDK and the `bookivox` CLI.
- **Single runtime dependency**: `httpx`.

## Requirements

- Python **3.11 or newer**.
- A Bookivox API key (`bookeys_sk-...`), created in
  [API keys](https://docs.bookivox.com/workspace/api-keys).

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install bookivox
```

```bash
uv add bookivox      # or: poetry add bookivox
```

Verify the installation:

```bash
python -c "import bookivox_sdk; print(bookivox_sdk.__version__)"
bookivox --version
```

## Authenticate

The API key is read from the `api_key` argument, then from `BOOKIVOX_API_KEY`:

```bash
export BOOKIVOX_API_KEY="bookeys_sk-..."
```

```python
import os
from bookivox_sdk import Bookivox

client = Bookivox(
    api_key=os.environ["BOOKIVOX_API_KEY"],  # or omit to use the env var
    timeout=30.0,
    max_retries=2,                           # idempotent requests only
)
```

| Parameter | Env var | Default |
| --- | --- | --- |
| `api_key` | `BOOKIVOX_API_KEY` | Required |
| `timeout` | none | `30.0` |
| `max_retries` | none | `2` |

The API origin is `https://api.bookivox.com` and is not configurable.

## Quick start

```python
import os
from bookivox_sdk import Bookivox

with Bookivox(api_key=os.environ["BOOKIVOX_API_KEY"]) as client:
    for workflow in client.list_workflows():
        print(workflow["id"], workflow.get("name"))
```

`Bookivox` is a context manager: `with` closes the underlying connection pool.

## Methods

| Method | HTTP | Description |
| --- | --- | --- |
| `list_workflows(*, status=None)` | `GET /workflow/fetch` | List the organization's agents |
| `get_workflow(workflow_id)` | `GET /workflow/fetch/{id}` | Fetch one agent |
| `create_workflow(body)` | `POST /workflow/create/definition` | Create an agent |
| `update_workflow(workflow_id, body)` | `PUT /workflow/{id}` | Update an agent |
| `list_node_types()` | `GET /node-types` | List node types and their specs |
| `get_node_type(name)` | `GET /node-types/{name}` | Fetch one node type spec |
| `list_tools(*, status=None, category=None)` | `GET /tools/` | List tools |
| `create_tool(body)` | `POST /tools/` | Create a tool |
| `list_documents(*, status=None, limit=None, offset=None)` | `GET /knowledge-base/documents` | List knowledge-base documents |
| `list_recordings(*, workflow_id=None, ...)` | `GET /workflow-recordings/` | List recordings |
| `list_credentials()` | `GET /credentials/` | List credentials |
| `test_phone_call(body)` | `POST /telephony/initiate-call` | Start a test call (**billable**) |

## Credentials

Credentials are created from the Bookivox UI or with a direct REST call
(`POST /api/v1/credentials`), then referenced by `credential_uuid` in a tool
definition. The SDK only lists them (`list_credentials`), so secrets never pass
through your code.

The `custom_header` credential type carries **multiple HTTP headers** and
**JSON body fields** in one reusable object — required by APIs that authenticate
in the body (for example Mews `ClientToken` / `AccessToken` / `Client`):

```json
{
  "name": "Mews Connector",
  "credential_type": "custom_header",
  "credential_data": {
    "headers": [{ "name": "X-Source", "value": "bookivox" }],
    "body": [
      { "name": "ClientToken", "value": "<client-token>" },
      { "name": "AccessToken", "value": "<access-token>" },
      { "name": "Client", "value": "<integration-name>" }
    ]
  }
}
```

Body fields are merged into every `POST`/`PUT`/`PATCH` JSON body (query params
for `GET`/`DELETE`) and take precedence over model- and preset-provided
parameters.

## Errors

```python
from bookivox_sdk import (
    Bookivox,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

try:
    with Bookivox() as client:
        client.get_workflow("wf_123")
except AuthenticationError:
    ...  # 401: invalid or revoked key
except NotFoundError:
    ...  # 404: unknown agent, or outside your organization
except ValidationError as exc:
    print(exc.status_code, exc.body)
except RateLimitError as exc:
    print("retry in", exc.retry_after, "s")
```

Every `APIStatusError` exposes `status_code`, `request_id` and `body`.

## CLI

```bash
bookivox login --api-key "$BOOKIVOX_API_KEY"
bookivox config
bookivox workflows list --json
```

Exit codes: `0` ok, `1` error, `2` usage, `3` auth, `4` not found,
`5` rate limit, `6` connection.

## Security

- Never commit `.env` files; load the key from your platform's secret manager.
- `test_phone_call` triggers a **real, billable phone call**.

## Generated code

`src/bookivox_sdk/models.py` and `src/bookivox_sdk/_generated.py` are generated
from the API OpenAPI schema and must never be edited by hand. Regenerate them
with `./generate_sdk.sh` from the repository root.

Full documentation: <https://docs.bookivox.com/sdk/overview>.
