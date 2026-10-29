# @bookivox/sdk

Official TypeScript SDK for the [Bookivox](https://bookivox.com) API: typed
access to agents, node types, tools, knowledge-base documents, recordings,
credentials and test calls.

- **Zero runtime dependency** — uses the global `fetch` (Node 18+, Bun, Deno, edge runtimes).
- **ESM only** — `"type": "module"`, `import` syntax.
- **Typed** — every method and payload ships with generated `.d.ts` declarations.
- **Safe by default** — timeouts, retries on idempotent verbs only, typed errors, no secret logging.

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
| `apiKey` | `BOOKIVOX_API_KEY` | — (required) |
| `timeoutMs` | — | `30000` |
| `maxRetries` | — | `2` |
| `fetch` | — | `globalThis.fetch` |

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

## Errors

```ts
import {
  AuthenticationError,
  NotFoundError,
  RateLimitError,
  ValidationError,
} from "@bookivox/sdk";

try {
  await client.getWorkflow("wf_123");
} catch (error) {
  if (error instanceof AuthenticationError) {
    // 401 — invalid or revoked key
  } else if (error instanceof NotFoundError) {
    // 404 — unknown agent, or outside your organization
  } else if (error instanceof ValidationError) {
    console.error(error.statusCode, error.body);
  } else if (error instanceof RateLimitError) {
    console.warn("retry in", error.retryAfterMs, "ms");
  }
}
```

Every `APIStatusError` exposes `statusCode`, `requestId` and `body`.

## Security

- Never ship an API key to a browser or a mobile app: keep the SDK on the server.
- Never commit `.env` files; load the key from your platform's secret manager.
- `testPhoneCall` triggers a **real, billable phone call**.

## Generated code

`src/types.ts` and `src/generated.ts` are generated from the API OpenAPI schema
and must never be edited by hand. Regenerate them with `./generate_sdk.sh` from
the repository root.

Full documentation: <https://docs.bookivox.com/sdk/overview>.
