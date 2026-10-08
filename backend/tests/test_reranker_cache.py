import sentence_transformers

from services import rag_service


def test_cross_encoder_is_loaded_once_and_top_n_is_per_call(monkeypatch):
    loads = []

    class FakeCrossEncoder:
        def __init__(self, *args, **kwargs):
            loads.append(args)

    monkeypatch.setattr(sentence_transformers, 'CrossEncoder', FakeCrossEncoder)
    monkeypatch.setattr(rag_service, '_reranker_base', None)

    first = rag_service.build_postprocessors(rerank=True, rerank_top_n=3)[0]
    second = rag_service.build_postprocessors(rerank=True, rerank_top_n=7)[0]

    assert len(loads) == 1
    assert (first.top_n, second.top_n) == (3, 7)
    assert first._model is second._model
