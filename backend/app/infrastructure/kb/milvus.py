"""Milvus 向量库：写入 embedding + 向量/关键词 RRF 检索。"""
from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.infrastructure.kb.chunk import Chunk
from app.infrastructure.kb.embed import embed_dim, embed_query, embed_texts
from app.infrastructure.kb.search import keyword_rank, rrf_fuse


class MilvusVectorStore:
    def __init__(self):
        self.uri = (settings.milvus_uri or "http://127.0.0.1:19530").strip()
        self.collection = (settings.milvus_collection or "jarvis_kb").strip()
        self._client = None

    @property
    def path(self) -> str:
        return f"{self.uri}/{self.collection}"

    def _get_client(self):
        if self._client is None:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=self.uri)
            self._ensure_collection()
        return self._client

    def _create_collection(self, client) -> None:
        from pymilvus import DataType, MilvusClient

        dim = embed_dim()
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=256)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="meta", datatype=DataType.JSON)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
        index_params = client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
        client.create_collection(
            collection_name=self.collection,
            schema=schema,
            index_params=index_params,
        )
        client.load_collection(self.collection)

    def _ensure_collection(self) -> None:
        client = self._client
        if client.has_collection(self.collection):
            client.load_collection(self.collection)
            return
        self._create_collection(client)

    def has_data(self) -> bool:
        client = self._get_client()
        if not client.has_collection(self.collection):
            return False
        try:
            stats = client.get_collection_stats(self.collection) or {}
            return int(stats.get("row_count") or 0) > 0
        except Exception:
            return False

    def rebuild(self, chunks: list[Chunk]) -> None:
        from pymilvus import MilvusClient

        client = self._get_client()
        if client.has_collection(self.collection):
            client.drop_collection(self.collection)
        self._client = MilvusClient(uri=self.uri)
        client = self._client
        self._create_collection(client)
        if not chunks:
            return
        vectors = embed_texts([c.text for c in chunks])
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for c, vec in zip(chunks, vectors):
            cid = str(c.id or "")[:256]
            if not cid or cid in seen:
                continue
            seen.add(cid)
            meta = c.meta or {}
            if not isinstance(meta, dict):
                try:
                    meta = json.loads(json.dumps(meta, default=str))
                except Exception:
                    meta = {"value": str(meta)}
            rows.append(
                {
                    "id": cid,
                    "text": (c.text or "")[:8192],
                    "source": (c.source or "")[:512],
                    "meta": meta,
                    "vector": vec,
                }
            )
        for i in range(0, len(rows), 64):
            client.insert(collection_name=self.collection, data=rows[i : i + 64])
        client.flush(self.collection)
        client.load_collection(self.collection)

    def _all_rows(self, client) -> list[dict[str, Any]]:
        try:
            raw = client.query(
                collection_name=self.collection,
                filter='id != ""',
                output_fields=["text", "source", "meta"],
                limit=16384,
            )
        except Exception:
            return []
        out = []
        for row in raw or []:
            out.append(
                {
                    "id": row.get("id"),
                    "text": row.get("text") or "",
                    "source": row.get("source") or "",
                    "meta": row.get("meta") or {},
                }
            )
        return out

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not (query or "").strip():
            return []
        try:
            client = self._get_client()
            if not client.has_collection(self.collection):
                return []
            hits = client.search(
                collection_name=self.collection,
                data=[embed_query(query)],
                limit=max(20, int(top_k) * 4),
                output_fields=["text", "source", "meta"],
                search_params={"metric_type": "COSINE", "params": {}},
            )
        except Exception as e:
            print(f"[kb] milvus search failed: {e}", flush=True)
            return []
        vector_hits = []
        for row in (hits[0] if hits else []):
            entity = row.get("entity") or {}
            vector_hits.append(
                {
                    "id": row.get("id"),
                    "text": entity.get("text") or "",
                    "source": entity.get("source") or "",
                    "meta": entity.get("meta") or {},
                    "score": round(float(row.get("distance") or 0), 4),
                }
            )
        kw_hits = keyword_rank(query, self._all_rows(client), top_k=20)
        return rrf_fuse(vector_hits, kw_hits, top_k=top_k)
