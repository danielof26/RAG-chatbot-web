"""
Self-contained RAPTOR retriever compatible with llama-index-core 0.14.x.

Adapted from llama-index-packs-raptor (deprecated, incompatible with core 0.14.x
because it depends on llama_index.core.llama_pack which was removed).
Credits to the original authors: https://github.com/run-llama/llama_index
"""

import asyncio
import random
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import umap
from sklearn.mixture import GaussianMixture

from llama_index.core import StorageContext, VectorStoreIndex, get_response_synthesizer, get_tokenizer
from llama_index.core.base.base_retriever import BaseRetriever, QueryType
from llama_index.core.bridge.pydantic import BaseModel, Field
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.ingestion import run_transformations
from llama_index.core.llms.llm import LLM
from llama_index.core.response_synthesizers import BaseSynthesizer
from llama_index.core.schema import BaseNode, NodeWithScore, QueryBundle, TextNode, TransformComponent
from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    MetadataFilter,
    MetadataFilters,
)

_RANDOM_SEED = 224
random.seed(_RANDOM_SEED)

DEFAULT_SUMMARY_PROMPT = "Summarize the provided text, including as many key details as needed."


# ---------------------------------------------------------------------------
# Clustering helpers (from llama_index/packs/raptor/clustering.py)
# ---------------------------------------------------------------------------

def _global_cluster_embeddings(embeddings: np.ndarray, dim: int, n_neighbors: Optional[int] = None) -> np.ndarray:
    if n_neighbors is None:
        n_neighbors = int((len(embeddings) - 1) ** 0.5)
    return umap.UMAP(n_neighbors=n_neighbors, n_components=dim, metric="cosine").fit_transform(embeddings)


def _local_cluster_embeddings(embeddings: np.ndarray, dim: int, num_neighbors: int = 10) -> np.ndarray:
    return umap.UMAP(n_neighbors=num_neighbors, n_components=dim, metric="cosine").fit_transform(embeddings)


def _get_optimal_clusters(embeddings: np.ndarray, max_clusters: int = 6) -> int:
    max_clusters = min(max_clusters, len(embeddings))
    if max_clusters < 2:
        return 1
    bics = []
    for n in np.arange(1, max_clusters):
        gm = GaussianMixture(n_components=n, random_state=_RANDOM_SEED)
        gm.fit(embeddings)
        bics.append(gm.bic(embeddings))
    return np.arange(1, max_clusters)[np.argmin(bics)]


def _gmm_cluster(embeddings: np.ndarray, threshold: float):
    n_clusters = _get_optimal_clusters(embeddings)
    gm = GaussianMixture(n_components=n_clusters, random_state=0)
    gm.fit(embeddings)
    probs = gm.predict_proba(embeddings)
    labels = [np.where(prob > threshold)[0] for prob in probs]
    return labels, n_clusters


def _perform_clustering(embeddings: np.ndarray, dim: int, threshold: float) -> List[np.ndarray]:
    if len(embeddings) <= dim + 1:
        return [np.array([0]) for _ in range(len(embeddings))]

    reduced = _global_cluster_embeddings(embeddings, dim)
    clusters, _ = _gmm_cluster(reduced, threshold)
    return clusters


def get_clusters(
    nodes: List[BaseNode],
    embedding_map: Dict[str, List[float]],
    max_length_in_cluster: int = 10000,
    tokenizer: Optional[Callable] = None,
    reduction_dimension: int = 10,
    threshold: float = 0.1,
    prev_total_length=None,
) -> List[List[BaseNode]]:
    tokenizer = tokenizer or get_tokenizer()
    embeddings = np.array([np.array(embedding_map[node.id_]) for node in nodes])
    clusters = _perform_clustering(embeddings, dim=reduction_dimension, threshold=threshold)

    node_clusters = []
    for label in np.unique(np.concatenate(clusters)):
        indices = [i for i, c in enumerate(clusters) if label in c]
        cluster_nodes = [nodes[i] for i in indices]
        if len(cluster_nodes) == 1:
            node_clusters.append(cluster_nodes)
            continue
        total_length = sum(len(tokenizer(n.text)) for n in cluster_nodes)
        if total_length > max_length_in_cluster and (prev_total_length is None or total_length < prev_total_length):
            node_clusters.extend(get_clusters(
                cluster_nodes, embedding_map,
                max_length_in_cluster=max_length_in_cluster,
                tokenizer=tokenizer,
                reduction_dimension=reduction_dimension,
                threshold=threshold,
                prev_total_length=total_length,
            ))
        else:
            node_clusters.append(cluster_nodes)

    return node_clusters


# ---------------------------------------------------------------------------
# SummaryModule
# ---------------------------------------------------------------------------

class SummaryModule(BaseModel):
    response_synthesizer: BaseSynthesizer = Field(description="LLM synthesizer")
    summary_prompt: str = Field(default=DEFAULT_SUMMARY_PROMPT)
    num_workers: int = Field(default=4)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, llm: Optional[LLM] = None, summary_prompt: str = DEFAULT_SUMMARY_PROMPT, num_workers: int = 4):
        response_synthesizer = get_response_synthesizer(response_mode="simple_summarize", use_async=True, llm=llm)
        super().__init__(response_synthesizer=response_synthesizer, summary_prompt=summary_prompt, num_workers=num_workers)

    async def generate_summaries(self, documents_per_cluster: List[List[BaseNode]]) -> List[str]:
        lock = asyncio.Semaphore(self.num_workers)
        responses = []
        for documents in documents_per_cluster:
            with_scores = [NodeWithScore(node=doc, score=1.0) for doc in documents]
            async with lock:
                responses.append(await self.response_synthesizer.asynthesize(self.summary_prompt, with_scores))
        return [str(r) for r in responses]


# ---------------------------------------------------------------------------
# RaptorRetriever
# ---------------------------------------------------------------------------

class RaptorRetriever(BaseRetriever):
    def __init__(
        self,
        documents: List[BaseNode],
        tree_depth: int = 3,
        similarity_top_k: int = 2,
        llm: Optional[LLM] = None,
        embed_model: Optional[BaseEmbedding] = None,
        vector_store: Optional[BasePydanticVectorStore] = None,
        transformations: Optional[List[TransformComponent]] = None,
        summary_module: Optional[SummaryModule] = None,
        existing_index: Optional[VectorStoreIndex] = None,
        mode: str = "collapsed",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.mode = mode
        self.summary_module = summary_module or SummaryModule(llm=llm)
        self.index = existing_index or VectorStoreIndex(
            nodes=[],
            storage_context=StorageContext.from_defaults(vector_store=vector_store),
            embed_model=embed_model,
            transformations=transformations,
        )
        self.tree_depth = tree_depth
        self.similarity_top_k = similarity_top_k

        if len(documents) > 0:
            asyncio.run(self._insert(documents))

    async def _insert(self, documents: List[BaseNode]) -> None:
        embed_model = self.index._embed_model
        transformations = self.index._transformations

        cur_nodes = run_transformations(documents, transformations, in_place=False)
        for level in range(self.tree_depth):
            print(f"[RAPTOR] Building level {level} ({len(cur_nodes)} nodes)...")
            embeddings = await embed_model.aget_text_embedding_batch(
                [node.get_content(metadata_mode="embed") for node in cur_nodes]
            )
            id_to_embedding = {node.id_: emb for node, emb in zip(cur_nodes, embeddings)}
            nodes_per_cluster = get_clusters(cur_nodes, id_to_embedding)
            print(f"[RAPTOR] Level {level}: {len(nodes_per_cluster)} clusters.")
            summaries = await self.summary_module.generate_summaries(nodes_per_cluster)

            new_nodes = [
                TextNode(
                    text=summary,
                    metadata={"level": level},
                    excluded_embed_metadata_keys=["level"],
                    excluded_llm_metadata_keys=["level"],
                )
                for summary in summaries
            ]

            seen_ids: set = set()
            nodes_with_emb = []
            for cluster, summary_node in zip(nodes_per_cluster, new_nodes):
                for node in cluster:
                    if node.id_ in seen_ids:
                        continue
                    seen_ids.add(node.id_)
                    node.metadata["parent_id"] = summary_node.id_
                    node.excluded_embed_metadata_keys.append("parent_id")
                    node.excluded_llm_metadata_keys.append("parent_id")
                    node.embedding = id_to_embedding[node.id_]
                    nodes_with_emb.append(node)

            self.index.insert_nodes(nodes_with_emb)
            cur_nodes = new_nodes

        self.index.insert_nodes(cur_nodes)

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        query_str = query_bundle.query_str if isinstance(query_bundle, QueryBundle) else query_bundle
        print(f"[RAPTOR] Retrieving (mode={self.mode}, top_k={self.similarity_top_k}): {query_str[:60]}")
        if self.mode == "collapsed":
            return self.index.as_retriever(similarity_top_k=self.similarity_top_k).retrieve(query_str)
        # tree_traversal needs async — create a fresh loop to avoid closed-loop issues
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._tree_traversal_retrieval(query_str))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    async def aretrieve(self, query_str_or_bundle: QueryType, mode: Optional[str] = None) -> List[NodeWithScore]:
        query_str = query_str_or_bundle.query_str if isinstance(query_str_or_bundle, QueryBundle) else query_str_or_bundle
        mode = mode or self.mode
        if mode == "collapsed":
            return await self.index.as_retriever(similarity_top_k=self.similarity_top_k).aretrieve(query_str)
        elif mode == "tree_traversal":
            return await self._tree_traversal_retrieval(query_str)
        raise ValueError(f"Unknown RAPTOR mode: {mode}")

    async def _tree_traversal_retrieval(self, query_str: str) -> List[NodeWithScore]:
        parent_ids = None
        selected = {}
        level = self.tree_depth - 1
        while level >= 0:
            if parent_ids is None:
                nodes = await self.index.as_retriever(
                    similarity_top_k=self.similarity_top_k,
                    filters=MetadataFilters(filters=[MetadataFilter(key="level", value=level)]),
                ).aretrieve(query_str)
                for n in nodes:
                    selected[n.id_] = n
                parent_ids = [n.id_ for n in nodes]
            elif parent_ids:
                nested = await asyncio.gather(*[
                    self.index.as_retriever(
                        similarity_top_k=self.similarity_top_k,
                        filters=MetadataFilters(filters=[MetadataFilter(key="parent_id", value=pid)]),
                    ).aretrieve(query_str)
                    for pid in parent_ids
                ])
                nodes = [n for sub in nested for n in sub]
                for n in nodes:
                    selected[n.id_] = n
                level -= 1
                parent_ids = None
            else:
                break
        return list(selected.values())
