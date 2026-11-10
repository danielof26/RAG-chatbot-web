"""Cache of structures derived from the chunks of a ChromaDB collection (BM25 index, keyword table, ...).

Building one means reading and tokenizing every chunk, so it is kept per collection and reused across requests.
An entry is valid while the collection keeps the same number of chunks, and is dropped explicitly whenever
documents are added or removed (see rag_service.invalidate_derived_indexes).
"""
import threading


class CollectionCache:
    def __init__(self, max_entries: int = 32):
        self._max_entries = max_entries
        self._entries = {}              # (collection name, kind) -> (chunk count, value)
        self._lock = threading.Lock()

    def get(self, collection, kind: str, build):
        """The value of `kind` for this collection; `build()` makes it when missing or out of date."""
        key, count = (collection.name, kind), collection.count()
        with self._lock:
            cached = self._entries.get(key)
            if cached is None or cached[0] != count:
                self._entries.pop(key, None)
                if len(self._entries) >= self._max_entries:
                    self._entries.pop(next(iter(self._entries)))
                cached = (count, build())
                self._entries[key] = cached
            return cached[1]

    def invalidate(self, collection_name: str):
        with self._lock:
            for key in [k for k in self._entries if k[0] == collection_name]:
                del self._entries[key]
