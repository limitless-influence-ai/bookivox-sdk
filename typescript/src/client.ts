/**
 * Bookivox TypeScript client.
 *
 * Zero runtime dependency: relies on the global `fetch` available in Node 18+,
 * Deno, Bun, Cloudflare Workers and browsers.
 */

import { GeneratedMethods } from "./generated.js";

export const DEFAULT_BASE_URL = "https://api.bookivox.com";
export const ENV_API_KEY = "BOOKIVOX_API_KEY";

/** Options forwarded to the transport by generated methods. */
export interface RequestOptions {
  /** Query string parameters; `undefined` and `null` values are dropped. */
  query?: Record<string, unknown>;
  /** JSON request body. */
  body?: unknown;
  /** Extra headers (merged after the defaults). */
  headers?: Record<string, string>;
  /** Caller-provided abort signal. */
  signal?: AbortSignal;
}

export interface BookivoxClientOptions {
  /** Organization API key (`bookeys_sk-...`). Defaults to `BOOKIVOX_API_KEY`. */
  apiKey?: string;
  /** Per-request timeout in milliseconds. */
  timeoutMs?: number;
  /** Retries for idempotent requests on transient failures. */
  maxRetries?: number;
  /** Inject a custom fetch implementation (proxies, instrumentation, tests). */
  fetch?: typeof globalThis.fetch;
}

export class BookivoxError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

/** The API could not be reached (DNS, TLS, connection reset, ...). */
export class APIConnectionError extends BookivoxError {}

/** The request timed out before a response was received. */
export class APITimeoutError extends APIConnectionError {}

/** The API answered with a non-2xx status code. */
export class APIStatusError extends BookivoxError {
  readonly statusCode: number;
  /** Correlation id echoed by the API, safe to log. */
  readonly requestId?: string;
  readonly body: unknown;

  constructor(
    message: string,
    statusCode: number,
    options: { requestId?: string; body?: unknown } = {},
  ) {
    super(message);
    this.statusCode = statusCode;
    this.requestId = options.requestId;
    this.body = options.body;
  }
}

export class AuthenticationError extends APIStatusError {}
export class PermissionDeniedError extends APIStatusError {}
export class NotFoundError extends APIStatusError {}
export class ConflictError extends APIStatusError {}
export class ValidationError extends APIStatusError {}
export class ServerError extends APIStatusError {}
export class RateLimitError extends APIStatusError {
  readonly retryAfterMs?: number;

  constructor(
    message: string,
    statusCode: number,
    options: { requestId?: string; body?: unknown; retryAfterMs?: number } = {},
  ) {
    super(message, statusCode, options);
    this.retryAfterMs = options.retryAfterMs;
  }
}

const RETRYABLE_METHODS = new Set(["GET", "HEAD", "PUT", "DELETE", "OPTIONS"]);
const RETRYABLE_STATUS = new Set([429, 500, 502, 503, 504]);
const MAX_RETRY_AFTER_MS = 30_000;

type Env = { [key: string]: string | undefined };

function readEnv(): Env {
  const processLike = (globalThis as { process?: { env?: Env } }).process;
  return processLike?.env ?? {};
}

function errorForStatus(
  statusCode: number,
  message: string,
  options: { requestId?: string; body?: unknown; retryAfterMs?: number },
): APIStatusError {
  switch (statusCode) {
    case 400:
      return new ValidationError(message, statusCode, options);
    case 401:
      return new AuthenticationError(message, statusCode, options);
    case 403:
      return new PermissionDeniedError(message, statusCode, options);
    case 404:
      return new NotFoundError(message, statusCode, options);
    case 409:
      return new ConflictError(message, statusCode, options);
    case 422:
      return new ValidationError(message, statusCode, options);
    case 429:
      return new RateLimitError(message, statusCode, options);
    default:
      return statusCode >= 500
        ? new ServerError(message, statusCode, options)
        : new APIStatusError(message, statusCode, options);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function retryAfterMs(response: Response): number | undefined {
  const raw = response.headers.get("retry-after");
  if (!raw) return undefined;
  const seconds = Number(raw);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds * 1000 : undefined;
}

export class Bookivox extends GeneratedMethods {
  readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly fetchImpl: typeof globalThis.fetch;

  constructor(options: BookivoxClientOptions = {}) {
    super();
    const env = readEnv();
    const apiKey = options.apiKey ?? env[ENV_API_KEY];
    if (!apiKey) {
      throw new BookivoxError(`Missing API key. Pass apiKey or set ${ENV_API_KEY}.`);
    }
    this.apiKey = apiKey;
    this.baseUrl = DEFAULT_BASE_URL;
    this.timeoutMs = options.timeoutMs ?? 30_000;
    this.maxRetries = Math.max(0, options.maxRetries ?? 2);
    this.fetchImpl = options.fetch ?? globalThis.fetch;
    if (typeof this.fetchImpl !== "function") {
      throw new BookivoxError("No global fetch available. Pass a fetch implementation.");
    }
  }

  protected async request<T>(
    method: string,
    path: string,
    options: RequestOptions = {},
  ): Promise<T> {
    const verb = method.toUpperCase();
    const url = new URL(`${this.baseUrl}${path}`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }

    const headers: Record<string, string> = {
      "X-API-Key": this.apiKey,
      Accept: "application/json",
      "User-Agent": "bookivox-typescript-sdk",
      ...options.headers,
    };
    const hasBody = options.body !== undefined;
    if (hasBody) headers["Content-Type"] = "application/json";

    const retryable = RETRYABLE_METHODS.has(verb);

    for (let attempt = 0; ; attempt += 1) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);
      const onAbort = () => controller.abort();
      options.signal?.addEventListener("abort", onAbort, { once: true });

      let response: Response;
      try {
        response = await this.fetchImpl(url, {
          method: verb,
          headers,
          body: hasBody ? JSON.stringify(options.body) : undefined,
          signal: controller.signal,
          redirect: "error",
        });
      } catch (error) {
        if (options.signal?.aborted) throw error;
        if (retryable && attempt < this.maxRetries) {
          await sleep(this.backoff(attempt));
          continue;
        }
        const aborted = error instanceof Error && error.name === "AbortError";
        throw aborted
          ? new APITimeoutError(`Request to ${path} timed out.`)
          : new APIConnectionError(
              `Could not reach the Bookivox API: ${error instanceof Error ? error.message : String(error)}`,
            );
      } finally {
        clearTimeout(timer);
        options.signal?.removeEventListener("abort", onAbort);
      }

      if (retryable && RETRYABLE_STATUS.has(response.status) && attempt < this.maxRetries) {
        const retryAfter = retryAfterMs(response);
        await sleep(
          retryAfter !== undefined ? Math.min(retryAfter, MAX_RETRY_AFTER_MS) : this.backoff(attempt),
        );
        continue;
      }

      if (!response.ok) {
        const { message, body } = await this.readError(response);
        throw errorForStatus(response.status, message, {
          requestId: response.headers.get("x-request-id") ?? undefined,
          body,
          retryAfterMs: retryAfterMs(response),
        });
      }

      if (response.status === 204) return undefined as T;
      const text = await response.text();
      if (!text) return undefined as T;
      if (!(response.headers.get("content-type") ?? "").includes("application/json")) {
        return text as unknown as T;
      }
      return JSON.parse(text) as T;
    }
  }

  private backoff(attempt: number): number {
    const base = Math.min(2 ** attempt * 1000, 8000);
    return base * (0.5 + Math.random() / 2);
  }

  private async readError(response: Response): Promise<{ message: string; body: unknown }> {
    const text = await response.text();
    let body: unknown = undefined;
    try {
      body = text ? JSON.parse(text) : undefined;
    } catch {
      body = text.slice(0, 500);
    }
    let message = `HTTP ${response.status}`;
    if (body && typeof body === "object") {
      const record = body as Record<string, unknown>;
      const detail = record.detail ?? record.message ?? record.error;
      if (typeof detail === "string" && detail) message = detail;
      else if (detail !== undefined) message = JSON.stringify(detail);
    } else if (typeof body === "string" && body) {
      message = body;
    }
    return { message, body };
  }
}
