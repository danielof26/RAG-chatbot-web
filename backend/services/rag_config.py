from dataclasses import dataclass, fields

from rag_catalog import MODE_PRIORITY, SYNTHESIS_PRIORITY


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


# name -> (type, min, max). Bounds keep a request from asking for absurd work (top_k of a million, ...).
_NUMBERS = {
    'similarity_top_k': (int, 1, 50),
    'chunk_size': (int, 64, 8192),
    'chunk_overlap': (int, 0, 2048),
    'temperature': (float, 0, 2),
    'similarity_cutoff': (float, 0, 1),
    'rerank_top_n': (int, 1, 50),
    'fusion_num_queries': (int, 1, 10),
    'conv_memory_turns': (int, 1, 20),
}
_BOOLEANS = ('sim_filter', 'rerank', 'xai', 'long_reorder', 'conv_memory')
_CHOICES = {
    'retrieval_mode': MODE_PRIORITY,
    'synthesis_mode': SYNTHESIS_PRIORITY,
    'conv_memory_mode': ['simple', 'condense'],
}


def _is_number(value, kind) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, int) if kind is int else isinstance(value, (int, float))


def validate_rag_config(data):
    """Returns an error message for the first invalid field of a rag_config sent by a client, else None.
    Only the known keys are checked; a null similarity_cutoff means "no cutoff"."""
    if not isinstance(data, dict):
        return 'rag_config must be an object'
    for name, (kind, low, high) in _NUMBERS.items():
        if name not in data or (name == 'similarity_cutoff' and data[name] is None):
            continue
        value = data[name]
        if not _is_number(value, kind) or not low <= value <= high:
            return f'{name} must be {"an integer" if kind is int else "a number"} between {low} and {high}'
    for name in _BOOLEANS:
        if name in data and not isinstance(data[name], bool):
            return f'{name} must be true or false'
    for name, allowed in _CHOICES.items():
        if name in data and data[name] not in allowed:
            return f'{name} must be one of: {", ".join(allowed)}'
    if data.get('chunk_overlap', 0) >= data.get('chunk_size', 512):
        return 'chunk_overlap must be smaller than chunk_size'
    return None
