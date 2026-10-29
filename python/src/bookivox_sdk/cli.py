"""``bookivox`` command line interface.

Design rules:

* Every command supports ``--json`` so it can be scripted safely.
* Destructive/billable commands require an explicit ``--yes``.
* The API key is read from ``--api-key``, ``BOOKIVOX_API_KEY`` or the local
  credential file (created by ``bookivox login``), in that order.
* Exit codes are stable: 0 success, 1 generic error, 2 usage, 3 auth,
  4 not found, 5 rate limited, 6 connection.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable

from . import credentials
from .client import DEFAULT_BASE_URL, ENV_API_KEY, Bookivox
from .errors import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BookivoxError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_NOT_FOUND = 4
EXIT_RATE_LIMIT = 5
EXIT_CONNECTION = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask(key: str) -> str:
    if len(key) <= 12:
        return "***"
    return f"{key[:12]}...{key[-4:]}"


def _resolve_api_key(cli_key: str | None) -> str | None:
    if cli_key:
        return cli_key
    env_key = os.environ.get(ENV_API_KEY)
    if env_key:
        return env_key
    stored = credentials.load().get("api_key")
    return stored if isinstance(stored, str) and stored else None


def _make_client(args: argparse.Namespace, *, require_key: bool = True) -> Bookivox:
    api_key = _resolve_api_key(getattr(args, "api_key", None))
    if require_key and not api_key:
        raise SystemExit(
            "No API key configured. Run `bookivox login --api-key <key>` "
            f"or set {ENV_API_KEY}."
        )
    return Bookivox(api_key or "", timeout=getattr(args, "timeout", 30.0))


def _read_json_body(path: str) -> Any:
    if path == "-":
        raw = sys.stdin.read()
        source = "stdin"
    else:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
        source = path
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid JSON in {source}: {exc}") from exc


def _print_json(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


def _print_table(payload: Any) -> None:
    rows = payload
    if isinstance(payload, dict):
        for key in ("items", "data", "results", "workflows", "tools", "documents", "recordings"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    if not isinstance(rows, list):
        _print_json(payload)
        return
    if not rows:
        print("(empty)")
        return
    if not all(isinstance(row, dict) for row in rows):
        _print_json(payload)
        return
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    widths = {
        column: max(
            len(column),
            *(len(_cell(row.get(column))) for row in rows),
        )
        for column in columns
    }
    print("  ".join(column.ljust(widths[column]) for column in columns))
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(_cell(row.get(column)).ljust(widths[column]) for column in columns))


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_login(args: argparse.Namespace) -> int:
    api_key = args.api_key or sys.stdin.readline().strip()
    if not api_key:
        print("No API key provided.", file=sys.stderr)
        return EXIT_USAGE
    data = credentials.load()
    data["api_key"] = api_key
    path = credentials.save(data)
    print(f"Credentials saved to {path}")
    return EXIT_OK


def cmd_logout(_args: argparse.Namespace) -> int:
    print("Logged out." if credentials.delete() else "No stored credentials.")
    return EXIT_OK


def cmd_config(args: argparse.Namespace) -> int:
    data = credentials.load()
    api_key = _resolve_api_key(getattr(args, "api_key", None))
    view = {
        "config_file": str(credentials.config_path()),
        "api_key": _mask(api_key) if api_key else None,
        "api_key_source": (
            "flag"
            if getattr(args, "api_key", None)
            else "env"
            if os.environ.get(ENV_API_KEY)
            else "file"
            if data.get("api_key")
            else None
        ),
        "base_url": DEFAULT_BASE_URL,
    }
    _print_json(view)
    return EXIT_OK


def _run(client: Bookivox, method: str, kwargs: dict[str, Any], args: argparse.Namespace) -> int:
    result = getattr(client, method)(**kwargs)
    if args.json:
        _print_json(result)
    else:
        _print_table(result)
    return EXIT_OK


def _body_args(args: argparse.Namespace) -> dict[str, Any]:
    if not args.file:
        raise SystemExit("Missing --file <path|-> (JSON request body).")
    return {"body": _read_json_body(args.file)}


def cmd_tools_list(args: argparse.Namespace) -> int:
    with _make_client(args) as client:
        return _run(client, "list_tools", {}, args)


def cmd_tools_create(args: argparse.Namespace) -> int:
    with _make_client(args) as client:
        return _run(client, "create_tool", _body_args(args), args)


def cmd_workflows_list(args: argparse.Namespace) -> int:
    with _make_client(args) as client:
        return _run(client, "list_workflows", {}, args)


def cmd_workflows_get(args: argparse.Namespace) -> int:
    with _make_client(args) as client:
        return _run(client, "get_workflow", {"workflow_id": args.workflow_id}, args)


def cmd_workflows_create(args: argparse.Namespace) -> int:
    with _make_client(args) as client:
        return _run(client, "create_workflow", _body_args(args), args)


def cmd_workflows_update(args: argparse.Namespace) -> int:
    with _make_client(args) as client:
        kwargs = {"workflow_id": args.workflow_id, **_body_args(args)}
        return _run(client, "update_workflow", kwargs, args)


def cmd_node_types_list(args: argparse.Namespace) -> int:
    with _make_client(args) as client:
        return _run(client, "list_node_types", {}, args)


def cmd_node_types_get(args: argparse.Namespace) -> int:
    with _make_client(args) as client:
        return _run(client, "get_node_type", {"name": args.name}, args)


def cmd_credentials_list(args: argparse.Namespace) -> int:
    with _make_client(args) as client:
        return _run(client, "list_credentials", {}, args)


def cmd_documents_list(args: argparse.Namespace) -> int:
    kwargs = {"status": args.status, "limit": args.limit, "offset": args.offset}
    with _make_client(args) as client:
        return _run(client, "list_documents", kwargs, args)


def cmd_recordings_list(args: argparse.Namespace) -> int:
    kwargs = {
        "workflow_id": args.workflow_id,
        "tts_provider": args.tts_provider,
        "tts_model": args.tts_model,
        "tts_voice_id": args.tts_voice_id,
    }
    with _make_client(args) as client:
        return _run(client, "list_recordings", kwargs, args)


def cmd_calls_test(args: argparse.Namespace) -> int:
    if not args.yes:
        print(
            "This command places a real, billable phone call. Re-run with --yes to confirm.",
            file=sys.stderr,
        )
        return EXIT_USAGE
    with _make_client(args) as client:
        return _run(client, "test_phone_call", _body_args(args), args)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    parser.add_argument("--api-key", help="API key (overrides env and stored credentials).")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds.")


def _add_body(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--file",
        "-f",
        required=True,
        help="Path to a JSON file, or '-' to read from stdin.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bookivox",
        description="Command line interface for the Bookivox API.",
    )
    parser.add_argument("--version", action="version", version="bookivox 0.1.1")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="Store an API key locally (0600 permissions).")
    login.add_argument("--api-key", help="API key (omit to read from stdin).")
    login.set_defaults(handler=cmd_login)

    logout = sub.add_parser("logout", help="Delete locally stored credentials.")
    logout.set_defaults(handler=cmd_logout)

    config = sub.add_parser("config", help="Show the effective configuration (key masked).")
    config.set_defaults(handler=cmd_config)

    tools = sub.add_parser("tools", help="Manage tools.").add_subparsers(dest="action", required=True)
    tools_list = tools.add_parser("list", help="List tools.")
    _add_common(tools_list)
    tools_list.set_defaults(handler=cmd_tools_list)
    tools_create = tools.add_parser("create", help="Create a tool from a JSON file.")
    _add_common(tools_create)
    _add_body(tools_create)
    tools_create.set_defaults(handler=cmd_tools_create)

    workflows = sub.add_parser("workflows", help="Manage workflows.").add_subparsers(
        dest="action", required=True
    )
    wf_list = workflows.add_parser("list", help="List workflows.")
    _add_common(wf_list)
    wf_list.set_defaults(handler=cmd_workflows_list)
    wf_get = workflows.add_parser("get", help="Fetch one workflow.")
    wf_get.add_argument("workflow_id")
    _add_common(wf_get)
    wf_get.set_defaults(handler=cmd_workflows_get)
    wf_create = workflows.add_parser("create", help="Create a workflow from a JSON definition.")
    _add_common(wf_create)
    _add_body(wf_create)
    wf_create.set_defaults(handler=cmd_workflows_create)
    wf_update = workflows.add_parser("update", help="Replace a workflow definition.")
    wf_update.add_argument("workflow_id")
    _add_common(wf_update)
    _add_body(wf_update)
    wf_update.set_defaults(handler=cmd_workflows_update)

    node_types = sub.add_parser("node-types", help="Inspect available node types.").add_subparsers(
        dest="action", required=True
    )
    nt_list = node_types.add_parser("list", help="List node types.")
    _add_common(nt_list)
    nt_list.set_defaults(handler=cmd_node_types_list)
    nt_get = node_types.add_parser("get", help="Fetch one node type spec.")
    nt_get.add_argument("name")
    _add_common(nt_get)
    nt_get.set_defaults(handler=cmd_node_types_get)

    creds = sub.add_parser("credentials", help="Manage credentials.").add_subparsers(
        dest="action", required=True
    )
    c_list = creds.add_parser("list", help="List credentials.")
    _add_common(c_list)
    c_list.set_defaults(handler=cmd_credentials_list)

    docs = sub.add_parser("documents", help="Knowledge base documents.").add_subparsers(
        dest="action", required=True
    )
    d_list = docs.add_parser("list", help="List documents.")
    d_list.add_argument("--status")
    d_list.add_argument("--limit", type=int)
    d_list.add_argument("--offset", type=int)
    _add_common(d_list)
    d_list.set_defaults(handler=cmd_documents_list)

    recs = sub.add_parser("recordings", help="Workflow recordings.").add_subparsers(
        dest="action", required=True
    )
    r_list = recs.add_parser("list", help="List recordings.")
    r_list.add_argument("--workflow-id", type=int)
    r_list.add_argument("--tts-provider")
    r_list.add_argument("--tts-model")
    r_list.add_argument("--tts-voice-id")
    _add_common(r_list)
    r_list.set_defaults(handler=cmd_recordings_list)

    calls = sub.add_parser("calls", help="Telephony operations.").add_subparsers(
        dest="action", required=True
    )
    c_test = calls.add_parser("test", help="Place a test call (billable — requires --yes).")
    _add_common(c_test)
    _add_body(c_test)
    c_test.add_argument("--yes", action="store_true", help="Confirm the billable call.")
    c_test.set_defaults(handler=cmd_calls_test)

    return parser


def _exit_code(exc: BaseException) -> int:
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return EXIT_AUTH
    if isinstance(exc, NotFoundError):
        return EXIT_NOT_FOUND
    if isinstance(exc, RateLimitError):
        return EXIT_RATE_LIMIT
    if isinstance(exc, APIConnectionError):
        return EXIT_CONNECTION
    if isinstance(exc, ValidationError):
        return EXIT_USAGE
    if isinstance(exc, APIStatusError):
        return EXIT_ERROR
    return EXIT_ERROR


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler
    try:
        return handler(args)
    except BookivoxError as exc:
        code = _exit_code(exc)
        payload = {"error": type(exc).__name__, "message": str(exc)}
        if isinstance(exc, APIStatusError):
            payload["status_code"] = exc.status_code
            if exc.request_id:
                payload["request_id"] = exc.request_id
        if getattr(args, "json", False):
            _print_json(payload)
        else:
            suffix = f" (HTTP {exc.status_code})" if isinstance(exc, APIStatusError) else ""
            print(f"Error: {exc}{suffix}", file=sys.stderr)
        return code
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
