##########################################
#
# External Retrieval Interface
#
##########################################
import asyncio
import json
import logging
import random
import uuid
from typing import Any, Optional

import httpx
import requests
from fastapi import HTTPException, status
from open_webui.internal.db import get_db
from open_webui.models.knowledge import Knowledge as DBKnowledge
from open_webui.models.knowledge import Knowledges
from pydantic import BaseModel, Field

CA_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"

log = logging.getLogger(__name__)


class EriConfig(BaseModel):
    host: str
    port: int
    token: str
    dataSource: str
    retrievalMethod: str
    query: str
    providerType: Optional[str] = "ANY"


class EriRetrievalRequest(BaseModel):
    latestUserPrompt: str
    latestUserPromptType: str = Field("TEXT")
    thread: dict = Field(default_factory=dict)
    retrievalProcessId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parameters: dict = Field(default_factory=dict)
    maxMatches: int = Field(0)


class EriQueryForm(BaseModel):
    eriConfig: EriConfig
    request: EriRetrievalRequest


def build_base_from_cfg(cfg: dict) -> str:
    host = (cfg.get("host") or "").strip()
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    port = cfg.get("port")
    if port:
        return f"{host.rstrip('/')}:{port}"
    return host.rstrip("/")


def eri_login(base: str, secret: dict) -> str | None:
    if not base or not secret:
        return None

    method = secret.get("authMethod") or secret.get("auth_method")
    if not method:
        return None

    url = f"{base}/auth?authMethod={method}"
    headers = {"accept": "application/json"}

    if method == "TOKEN":
        access_token = secret.get("access_token") or secret.get("token")
        if not access_token:
            return None
        headers["Authorization"] = f"Bearer {access_token}"
    elif method == "USERNAME_PASSWORD":
        username = secret.get("username")
        password = secret.get("password")
        if not username or not password:
            return None
        headers["user"] = username
        headers["password"] = password

    try:
        resp = requests.post(
            url,
            headers=headers,
            json={},
            verify=CA_BUNDLE,
        )
        data = resp.json()
        if resp.ok and data.get("success"):
            return data.get("token")
        else:
            log.warning("ERI auth failed: %s %s", resp.status_code, resp.text)
    except Exception as e:
        log.exception("ERI auth exception", exc_info=e)
    return None


def force_eri_reauth_for_knowledge(k: DBKnowledge) -> DBKnowledge:
    data = k.data or {}
    eri_cfg = data.get("eri_config") or {}
    base = build_base_from_cfg(eri_cfg)

    secret = k.eri_secret or {}
    if isinstance(secret, str):
        try:
            secret = json.loads(secret)
        except Exception:
            secret = {}

    if not base or not secret:
        return k

    new_token = eri_login(base, secret)
    if not new_token:
        return k

    eri_cfg["token"] = new_token
    data["eri_config"] = eri_cfg
    k.data = data

    with get_db() as db:
        db_obj = db.merge(k)
        db.commit()
        db.refresh(db_obj)

    return db_obj


def find_kb_by_key(key: str) -> Optional[Any]:
    kb = Knowledges.get_knowledge_by_id(key)

    if kb:
        return kb
    try:
        for x in Knowledges.get_knowledge_bases():
            if (
                getattr(x, "id", None) == key
                or getattr(x, "name", None) == key
                or getattr(x, "collection_name", None) == key
            ):
                return x
    except Exception:
        pass
    return None


def is_eri_collection(key: str) -> bool:
    kb = find_kb_by_key(key)
    return bool(kb and (kb.data or {}).get("data_source") == "eri")


async def eri_query(form: EriQueryForm):
    conf = form.eriConfig

    host = conf.host.strip()
    if not host.startswith(("http://", "https://")):
        host = "http://" + host

    base = host.rstrip("/") + f":{conf.port}"
    url = f"{base}/retrieval"

    token = conf.token

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}",
        "token": conf.token,
        "providerType": conf.providerType or "ANY",
        "Content-Type": "application/json",
    }

    body = form.request.dict()
    body["parameters"]["dataSource"] = conf.dataSource
    body["parameters"]["retrievalMethod"] = conf.retrievalMethod

    async with httpx.AsyncClient(
        timeout=60,
        verify=CA_BUNDLE,
    ) as client:
        resp = await client.post(url, json=body, headers=headers)

    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ERI auth failed: token invalid or expired",
        )

    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ERI returned {resp.status_code}: {resp.text}",
        )

    return resp.json()


# ERI-Hook
async def query_eri_if_applicable(collection_key: str, query: str, k: int):
    kb = find_kb_by_key(collection_key)

    if not kb or (kb.data or {}).get("data_source") != "eri":
        return None

    cfg = kb.data["eri_config"]
    form = EriQueryForm(
        eriConfig=EriConfig(**{**cfg, "query": query}),
        request=EriRetrievalRequest(
            latestUserPrompt=query,
            maxMatches=int(k) if isinstance(k, int) else 0,
        ),
    )

    last_err = None
    max_retries = 2
    base_backoff = 1.5
    jitter_factor = 0.3

    for attempt in range(1, max_retries + 1):
        try:
            resp = await eri_query(form)
            break
        except HTTPException as e:
            if e.status_code == 401 and attempt < max_retries:
                db_k = Knowledges.get_knowledge_with_secret_by_id(kb.id)
                if db_k:
                    db_k = force_eri_reauth_for_knowledge(db_k)
                    new_cfg = (db_k.data or {}).get("eri_config") or {}
                    form.eriConfig.token = new_cfg.get("token") or form.eriConfig.token
                    continue
            raise
        except (httpx.ReadTimeout, httpx.ConnectError) as e:
            last_err = e
            if attempt == max_retries:
                raise
            delay = base_backoff * (2 ** (attempt - 1))
            delay *= random.uniform(1 - jitter_factor, 1 + jitter_factor)
            await asyncio.sleep(delay)
    else:
        raise last_err

    raw_hits = resp if isinstance(resp, list) else (resp.get("matches") or [])
    if not raw_hits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ERI context found for this query",
        )

    limit = int(k) if isinstance(k, int) else 0
    hits = raw_hits if limit <= 0 else raw_hits[:limit]

    display_name = (
        getattr(kb, "name", None) or getattr(kb, "collection_name", None) or "Knowledge"
    )

    docs = [h.get("matchedContent", "") for h in hits]
    metas = [
        {
            "source": h.get("source") or h.get("name"),
            "category": h.get("category"),
            "type": h.get("type"),
            "source_name": display_name,
            "collection_name": display_name,
        }
        for h in hits
    ]

    return {
        "ids": [[str(uuid.uuid4()) for _ in hits]],
        "documents": [docs],
        "metadatas": [metas],
    }
