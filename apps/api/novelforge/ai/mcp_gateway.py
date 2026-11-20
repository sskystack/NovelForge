"""Opt-in MCP SDK client, with per-author registrations and a deny-by-default allowlist.

Each operation owns and closes its SDK session/transport. No roots, sampling or
elicitation capabilities are granted. A server annotation never grants write access.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

import anyio
import httpx
from fastapi import APIRouter, Depends
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from referencing import Registry
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelforge.ai.agent_models import MCPServer
from novelforge.ai.local_config import validate_endpoint
from novelforge.database import get_db
from novelforge.errors import Problem
from novelforge.identity.dependencies import get_current_user, require_csrf
from novelforge.identity.models import User

router = APIRouter(prefix="/mcp/servers", tags=["mcp"])


def validate_input_schema(schema: dict):
    if len(json.dumps(schema, ensure_ascii=False).encode("utf-8")) > 32000:
        raise ValueError("MCP input schema exceeds the schema budget")
    nodes = 0

    def visit(value, depth=0):
        nonlocal nodes
        nodes += 1
        if depth > 20 or nodes > 2000:
            raise ValueError("MCP schema exceeds the depth or node budget")
        if isinstance(value, dict):
            for keyword in ("$ref", "$dynamicRef", "$recursiveRef"):
                if keyword in value and not str(value[keyword]).startswith("#"):
                    raise ValueError("Remote JSON schema references are not permitted")
            for child in value.values():
                visit(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                visit(child, depth + 1)

    visit(schema)
    Draft202012Validator.check_schema(schema)


def deny_schema_retrieval(uri):
    raise ValueError("External JSON schema retrieval is disabled")


class MCPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    transport: Literal["stdio", "streamable-http"] = "stdio"
    command: str = Field(default="", max_length=2000)
    args: list[str] = Field(default_factory=list, max_length=50)
    url: str = Field(default="", max_length=2000)
    allowed_tools: list[str] = Field(default_factory=list, max_length=100)
    enabled: bool = False
    timeout_seconds: float = Field(default=10, ge=0.2, le=60)
    bearer_token: str | None = Field(default=None, max_length=4000, repr=False)

    @model_validator(mode="after")
    def safe_endpoint(self):
        if self.transport == "stdio":
            if not Path(self.command).is_absolute() or not Path(self.command).is_file():
                raise ValueError("stdio requires an existing absolute executable path.")
            if any(len(arg) > 8000 or "\x00" in arg for arg in self.args):
                raise ValueError("Invalid stdio argument.")
        else:
            self.url = validate_endpoint(self.url)
            if not self.url:
                raise ValueError("Streamable HTTP requires a URL.")
        return self


class MCPConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    transport: Literal["stdio", "streamable-http"] | None = None
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    allowed_tools: list[str] | None = None
    enabled: bool | None = None
    timeout_seconds: float | None = None
    bearer_token: str | None = Field(default=None, repr=False)


def serialize_server(row: MCPServer) -> dict:
    config = {key: value for key, value in row.configuration.items() if key != "bearer_token"}
    return {
        "id": str(row.id),
        "name": row.name,
        **config,
        "status": row.status,
        "last_error": row.last_error,
        "bearer_token_configured": bool(row.configuration.get("bearer_token")),
    }


def owned_server(db: Session, owner_id: UUID, server_id: UUID) -> MCPServer:
    row = db.scalar(
        select(MCPServer).where(MCPServer.id == server_id, MCPServer.owner_id == owner_id)
    )
    if row is None:
        raise Problem(404, "MCP_SERVER_NOT_FOUND", "Server not found", "No such MCP registration.")
    return row


@asynccontextmanager
async def connection(config: dict):
    timeout = config.get("timeout_seconds", 10)
    # fail_after surrounds session ownership so SDK task groups close in the same
    # task that entered them, including on cancellation and timeout.
    with anyio.fail_after(timeout):
        if config["transport"] == "stdio":
            params = StdioServerParameters(
                command=config["command"],
                args=config.get("args", []),
                env={
                    key: os.environ[key]
                    for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
                    if key in os.environ
                },
            )
            with open(os.devnull, "w") as errlog:
                async with stdio_client(params, errlog=errlog) as streams:
                    async with ClientSession(
                        *streams, read_timeout_seconds=timedelta(seconds=timeout)
                    ) as session:
                        await session.initialize()
                        yield session
        else:
            headers = (
                {"Authorization": f"Bearer {config['bearer_token']}"}
                if config.get("bearer_token")
                else {}
            )
            async with httpx.AsyncClient(
                headers=headers, timeout=timeout, trust_env=False, follow_redirects=False
            ) as http_client:
                async with streamable_http_client(
                    config["url"], http_client=http_client
                ) as streams:
                    async with ClientSession(
                        streams[0], streams[1], read_timeout_seconds=timedelta(seconds=timeout)
                    ) as session:
                        await session.initialize()
                        yield session


async def discover(config: dict, *, allowed_only: bool = True) -> list[dict]:
    async with connection(config) as session:
        result = []
        cursor = None
        for _ in range(10):
            page = await session.list_tools(cursor=cursor)
            for tool in page.tools:
                if not allowed_only or tool.name in config.get("allowed_tools", []):
                    validate_input_schema(tool.inputSchema)
                    result.append(
                        {
                            "name": tool.name,
                            "description": (tool.description or "")[:1000],
                            "input_schema": tool.inputSchema,
                        }
                    )
            cursor = page.nextCursor
            if not cursor:
                return result[:100]
        raise ValueError("MCP tool listing exceeds the pagination budget")


async def call(config: dict, name: str, arguments: dict, schema: dict) -> dict:
    if name not in config.get("allowed_tools", []):
        raise ValueError("MCP tool is not allowlisted")
    validate_input_schema(schema)
    Draft202012Validator(schema, registry=Registry(retrieve=deny_schema_retrieval)).validate(
        arguments
    )
    async with connection(config) as session:
        result = await session.call_tool(name, arguments)
        data = result.model_dump(mode="json", exclude_none=True)
        if len(json.dumps(data, ensure_ascii=False).encode("utf-8")) > 64000:
            raise ValueError("MCP result exceeds the 64 KB result budget")
        if result.isError:
            raise ValueError("MCP server reported a tool failure")
        return data


@router.get("")
def list_servers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [
        serialize_server(row)
        for row in db.scalars(
            select(MCPServer)
            .where(MCPServer.owner_id == user.id)
            .order_by(MCPServer.name, MCPServer.id)
        ).all()
    ]


@router.post("", status_code=201)
def register_server(
    payload: MCPConfig,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    row = MCPServer(
        owner_id=user.id, name=payload.name, configuration=payload.model_dump(exclude_none=True)
    )
    db.add(row)
    db.commit()
    return serialize_server(row)


@router.get("/{server_id}")
def get_server(
    server_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return serialize_server(owned_server(db, user.id, server_id))


@router.patch("/{server_id}")
def update_server(
    server_id: UUID,
    payload: MCPConfigPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    row = owned_server(db, user.id, server_id)
    try:
        merged = MCPConfig.model_validate(
            {**row.configuration, **payload.model_dump(exclude_unset=True, exclude_none=True)}
        )
    except ValidationError as exc:
        raise Problem(
            422,
            "INVALID_MCP_CONFIGURATION",
            "Invalid MCP configuration",
            "The merged MCP registration is invalid; check its endpoint and limits.",
        ) from exc
    row.configuration = merged.model_dump(exclude_none=True)
    row.name, row.status, row.last_error = merged.name, "disconnected", None
    db.commit()
    return serialize_server(row)


@router.delete("/{server_id}", status_code=204)
def remove_server(
    server_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    db.delete(owned_server(db, user.id, server_id))
    db.commit()


@router.post("/{server_id}/test")
async def test_server(
    server_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    row = owned_server(db, user.id, server_id)
    try:
        tools = await discover(row.configuration, allowed_only=False)
        # Connections are intentionally per-operation; never claim an idle live socket.
        row.status, row.last_error = "available", None
        db.commit()
        return {"ok": True, "server": serialize_server(row), "tools": tools}
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        row.status, row.last_error = (
            "error",
            "Connection or discovery failed; verify the server and allowlist.",
        )
        db.commit()
        raise Problem(
            502, "MCP_CONNECTION_FAILED", "MCP connection failed", row.last_error
        ) from exc
