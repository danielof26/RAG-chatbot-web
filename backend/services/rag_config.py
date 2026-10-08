from dataclasses import dataclass, fields


@dataclass(frozen=True)
class RagConfig:
    """Typed view over an agent's/snapshot's `rag_config` dict. Single place for keys and defaults."""
    similarity_top_k: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 50
    temperature: float = 0.1
    retrieval_mode: str = 'naive'
    synthesis_mode: str = 'compact'
    sim_filter: bool = False
    similarity_cutoff: float = None
    rerank: bool = False
    rerank_top_n: int = 3
    fusion_num_queries: int = 1
    xai: bool = False
    long_reorder: bool = False
    conv_memory: bool = False
    conv_memory_mode: str = 'simple'
    conv_memory_turns: int = 3

    @classmethod
    def from_dict(cls, data: dict = None) -> 'RagConfig':
        """Missing keys take the defaults; unknown keys are ignored. Stored values are not coerced."""
        data = data or {}
        return cls(**{f.name: data[f.name] for f in fields(cls) if f.name in data})

    @property
    def effective_cutoff(self):
        """Similarity cutoff to apply, or None when the filter is disabled."""
        return self.similarity_cutoff if self.sim_filter else None
