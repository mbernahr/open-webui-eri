##########################################
#
# External Retrieval Interface
#
##########################################
import asyncio
import json
import logging
import os
import random
import uuid
import re
from collections import Counter
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
HTTP_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _basename_without_ext(value: str) -> str:
    try:
        candidate = os.path.basename(value.strip())
        if not candidate:
            return ""
        stem, _ = os.path.splitext(candidate)
        return (stem or candidate).strip()
    except Exception:
        return ""


def _normalize_hit_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for key in (
            "matchedContent",
            "matched_content",
            "content",
            "text",
            "snippet",
            "page_content",
            "document",
        ):
            nested = _normalize_hit_text(value.get(key))
            if nested:
                return nested
        return ""

    if isinstance(value, list):
        parts = [_normalize_hit_text(item) for item in value]
        parts = [part for part in parts if part]
        return "\n\n".join(parts)

    if value is None:
        return ""

    return str(value).strip()


def _extract_hit_text(hit: dict) -> tuple[str, str]:
    for field in (
        "matchedContent",
        "matched_content",
        "content",
        "text",
        "snippet",
        "page_content",
        "document",
    ):
        normalized = _normalize_hit_text(hit.get(field))
        if normalized:
            return normalized, field

    surrounding = _normalize_hit_text(hit.get("surroundingContent"))
    if surrounding:
        return surrounding, "surroundingContent"

    return "", "empty"


def _metadata_fallback_text(hit: dict) -> str:
    parts: list[str] = []

    routine_id = hit.get("routine_id")
    if isinstance(routine_id, str) and routine_id.strip():
        parts.append(f"Routine ID: {routine_id.strip()}")

    for key in ("name", "title", "filename", "path", "source", "category", "type"):
        value = hit.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                if key in ("filename", "path", "source"):
                    label = key.capitalize()
                    parts.append(f"{label}: {normalized}")
                    basename = _basename_without_ext(normalized)
                    if basename and basename != normalized:
                        parts.append(f"Document: {basename}")
                else:
                    parts.append(f"{key.capitalize()}: {normalized}")

    links = hit.get("links")
    if isinstance(links, list):
        for link in links:
            if isinstance(link, str) and link.strip():
                parts.append(f"Link: {link.strip()}")
                break

    # Keep it compact but informative enough for prompt usage.
    deduped: list[str] = []
    seen = set()
    for part in parts:
        if part not in seen:
            seen.add(part)
            deduped.append(part)

    return "\n".join(deduped).strip()


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
    # Do not apply an additional local hard cap here.
    # The ERI backend already receives `maxMatches` and should be the single source of truth.
    hits = raw_hits

    display_name = (
        getattr(kb, "name", None) or getattr(kb, "collection_name", None) or "Knowledge"
    )

    docs: list[str] = []
    text_field_usage = Counter()
    metas = []
    fallback_texts = 0
    for hit in hits:
        doc_text, text_field = _extract_hit_text(hit)
        if not doc_text:
            doc_text = _metadata_fallback_text(hit)
            if doc_text:
                text_field = "metadata_fallback"
                fallback_texts += 1
        docs.append(doc_text)
        text_field_usage[text_field] += 1

        source_value = hit.get("source") or hit.get("path") or hit.get("name")
        path_value = hit.get("path") or source_value

        links_value = hit.get("links")
        if not isinstance(links_value, list):
            links_value = []

        if (
            isinstance(source_value, str)
            and HTTP_URL_RE.match(source_value)
            and source_value not in links_value
        ):
            links_value = [source_value, *links_value]

        metas.append(
            {
                "source": source_value,
                "path": path_value,
                "links": links_value,
                "filename": hit.get("filename"),
                "name": hit.get("name"),
                "category": hit.get("category"),
                "type": hit.get("type"),
                "_text_field": text_field,
                "source_name": display_name,
                "collection_name": display_name,
            }
        )

    preview = []
    for idx, hit in enumerate(hits[:5]):
        links = hit.get("links")
        first_link = links[0] if isinstance(links, list) and links else None
        preview.append(
            {
                "name": hit.get("name"),
                "path": hit.get("path"),
                "source": hit.get("source"),
                "link": first_link,
                "text_field": metas[idx].get("_text_field") if idx < len(metas) else "empty",
                "text_len": len(docs[idx]) if idx < len(docs) else 0,
            }
        )

    log.info(
        "ERI trace: key=%s query=%s requested_limit=%d raw_hits=%d used_hits=%d non_empty_texts=%d fallback_texts=%d text_fields=%s",
        collection_key,
        query[:200],
        limit,
        len(raw_hits),
        len(hits),
        sum(1 for doc in docs if doc.strip()),
        fallback_texts,
        dict(text_field_usage),
    )
    if preview:
        log.info("ERI trace preview: %s", preview)

    return {
        "ids": [[str(uuid.uuid4()) for _ in hits]],
        "documents": [docs],
        "metadatas": [metas],
    }
