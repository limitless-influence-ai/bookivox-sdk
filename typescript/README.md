# @bookivox/sdk

Official TypeScript SDK for the [Bookivox](https://bookivox.com) API: typed access
to agents, node types, tools, knowledge-base documents, recordings, credentials
and test calls.

- **Zero runtime dependency**: uses the global `fetch` (Node 18+, Bun, Deno, edge runtimes).
- **ESM only**: `"type": "module"`, `import` from `@bookivox/sdk`.
- **Typed**: every method and payload ships with generated `.d.ts` declarations.
- **Safe by default**: timeouts, retries on idempotent verbs only, typed errors, no secret logging.
- **Fixed origin**: always talks to `https://api.bookivox.com`, nothing to configure.

## Requirements

- Node.js **18 or newer** (or Bun / Deno).
- A Bookivox API key (`bookeys_sk-...`), created in
  [API keys](https://docs.bookivox.com/workspace/api-keys).

## Install

```bash
npm install @bookivox/sdk
```

```bash
pnpm add @bookivox/sdk
yarn add @bookivox/sdk
bun add @bookivox/sdk
```

Verify the installation:

```bash
node -e "import('@bookivox/sdk').then(m => console.log(m.Bookivox.name))"
```

Recommended `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "lib": ["ES2022", "DOM"]
  }
}
```

## Authenticate

The API key is read from the `apiKey` option, then from `BOOKIVOX_API_KEY`:

```bash
export BOOKIVOX_API_KEY="bookeys_sk-..."
```

```ts
import { Bookivox } from "@bookivox/sdk";

const client = new Bookivox({
  apiKey: process.env.BOOKIVOX_API_KEY, // or omit to use the env var
  timeoutMs: 30_000,
  maxRetries: 2,                        // idempotent requests only
});
```

| Option | Env var | Default |
| --- | --- | --- |
| `apiKey` | `BOOKIVOX_API_KEY` | Required |
| `timeoutMs` | none | `30000` |
| `maxRetries` | none | `2` |
| `fetch` | none | `globalThis.fetch` |

The API origin is `https://api.bookivox.com` and is not configurable.

## Quick start

```ts
import { Bookivox } from "@bookivox/sdk";

const client = new Bookivox({ apiKey: process.env.BOOKIVOX_API_KEY! });

const workflows = await client.listWorkflows();
for (const workflow of workflows) {
  console.log(workflow.id, workflow.name);
}
```

## Methods

| Method | HTTP | Description |
| --- | --- | --- |
| `listWorkflows(options?)` | `GET /workflow/fetch` | List the organization's agents |
| `getWorkflow(workflowId)` | `GET /workflow/fetch/{id}` | Fetch one agent |
| `createWorkflow(body)` | `POST /workflow/create/definition` | Create an agent |
| `updateWorkflow(workflowId, body)` | `PUT /workflow/{id}` | Update an agent |
| `listNodeTypes()` | `GET /node-types` | List node types and their specs |
| `getNodeType(name)` | `GET /node-types/{name}` | Fetch one node type spec |
| `listTools(options?)` | `GET /tools/` | List tools |
| `createTool(body)` | `POST /tools/` | Create a tool |
| `listDocuments(options?)` | `GET /knowledge-base/documents` | List knowledge-base documents |
| `listRecordings(options?)` | `GET /workflow-recordings/` | List recordings |
| `listCredentials()` | `GET /credentials/` | List credentials |
| `testPhoneCall(body)` | `POST /telephony/initiate-call` | Start a test call (**billable**) |

## Filtering and pagination

List methods accept optional filters. Documents are pageable with `limit` and `offset`:

```ts
// Only active agents
const active = await client.listWorkflows({ status: "active" });

// Tools by category
const tools = await client.listTools({ category: "http" });

// First page of 25 knowledge-base documents
const page = await client.listDocuments({ limit: 25, offset: 0 });
```

```ts
// Recordings for a single agent
const recordings = await client.listRecordings({ workflowId: 42 });
```

## Node types

A node type describes one building block of an agent (its inputs, outputs and
configuration). Fetch the catalog once, then read a single spec:

```ts
const catalog = await client.listNodeTypes();
const spec = await client.getNodeType("llm");
```

## Create and update an agent

`createWorkflow` requires `name` and `workflow_definition`:

```ts
const created = await client.createWorkflow({
  name: "Support inbound",
  workflow_definition: {
    // nodes and edges, validated by the API
  },
});

await client.updateWorkflow(created.id, {
  name: "Support inbound (EU)",
  // only the fields to change, typed as UpdateWorkflowRequest
});
```

## Test calls

```ts
const call = await client.testPhoneCall({
  // typed as InitiateCallRequest
});
```

This triggers a **real, billable phone call**. Keep it out of test suites that run
against production.

## Errors

```ts
import {
  APIConnectionError,
  APITimeoutError,
  AuthenticationError,
  NotFoundError,
  RateLimitError,
  ValidationError,
} from "@bookivox/sdk";

try {
  await client.getWorkflow("wf_123");
} catch (error) {
  if (error instanceof AuthenticationError) {
    // 401: invalid or revoked key
  } else if (error instanceof NotFoundError) {
    // 404: unknown agent, or outside your organization
  } else if (error instanceof ValidationError) {
    console.error(error.statusCode, error.body); // 400 or 422
  } else if (error instanceof RateLimitError) {
    console.warn("retry in", error.retryAfterMs, "ms"); // 429
  } else if (error instanceof APITimeoutError) {
    // no response within timeoutMs
  } else if (error instanceof APIConnectionError) {
    // DNS, TLS, connection reset
  }
}
```

Every `APIStatusError` exposes `statusCode`, `requestId` and `body`. The request id
is echoed by the API and is safe to log and to quote in a support request.

| Status | Error class |
| --- | --- |
| `400`, `422` | `ValidationError` |
| `401` | `AuthenticationError` |
| `403` | `PermissionDeniedError` |
| `404` | `NotFoundError` |
| `409` | `ConflictError` |
| `429` | `RateLimitError` |
| `5xx` | `ServerError` |

## Timeouts, retries and cancellation

- `timeoutMs` applies to each request; exceeding it throws `APITimeoutError`.
- `maxRetries` retries **idempotent verbs only** (`GET`, `HEAD`, `PUT`, `DELETE`,
  `OPTIONS`) on `429`, `500`, `502`, `503` and `504`, with exponential backoff.
- A `Retry-After` header is honoured up to 30 seconds.
- Pass a custom `fetch` to hook proxies, tracing or tests without patching globals.

## Types

Response and request types are re-exported from the package root:

```ts
import type { WorkflowResponse, CreateWorkflowRequest } from "@bookivox/sdk";
```

## Security

- Never ship an API key to a browser or a mobile app: keep the SDK on the server.
- Never commit `.env` files; load the key from your platform's secret manager.
- The SDK never logs the API key nor request bodies.
- `testPhoneCall` triggers a **real, billable phone call**.

## Generated code

`src/types.ts` and `src/generated.ts` are generated from the API OpenAPI schema
and must never be edited by hand. Regenerate them with `./generate_sdk.sh` from
the repository root.

## Links

| Resource | Link |
| --- | --- |
| Documentation | <https://docs.bookivox.com/sdk/overview> |
| TypeScript guide | <https://docs.bookivox.com/sdk/typescript> |
| Installation guide | <https://docs.bookivox.com/sdk/installation> |
| Source code | <https://github.com/limitless-influence-ai/bookivox-sdk> |
| Issues | <https://github.com/limitless-influence-ai/bookivox-sdk/issues> |
| License | MIT |

Full documentation: <https://docs.bookivox.com/sdk/overview>.
