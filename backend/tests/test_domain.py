import dataclasses

import pytest

from rag_catalog import get_catalog
from services.rag_config import RagConfig
from states import (
    DOCUMENT_TRANSITIONS, RUN_TRANSITIONS, DocumentStatus, RunStatus, blocked_sources,
)


def test_rag_config_defaults_and_unknown_keys():
    cfg = RagConfig.from_dict({'similarity_top_k': 9, 'not_a_field': 1})
    assert cfg.similarity_top_k == 9 and cfg.chunk_size == 512
    assert RagConfig.from_dict(None) == RagConfig()


def test_rag_config_effective_cutoff_requires_sim_filter():
    assert RagConfig(similarity_cutoff=0.4, sim_filter=False).effective_cutoff is None
    assert RagConfig(similarity_cutoff=0.4, sim_filter=True).effective_cutoff == 0.4


def test_rag_config_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        RagConfig().rerank = True


def test_catalog_incompatibilities_are_symmetric_and_reference_real_techniques():
    techs = {t['id']: t for s in get_catalog()['sections'] for t in s['techniques']}
    for tid, tech in techs.items():
        for other in tech['incompat']:
            assert other in techs, f'{tid} references unknown technique {other}'
            assert tid in techs[other]['incompat'], f'{tid} -> {other} is not symmetric'


def test_catalog_does_not_mutate_between_calls():
    assert get_catalog() == get_catalog()


def test_document_transitions():
    assert set(blocked_sources(DocumentStatus.INDEXING, DOCUMENT_TRANSITIONS)) == {'indexing'}
    assert DocumentStatus.INDEXED in DOCUMENT_TRANSITIONS[DocumentStatus.INDEXING]


def test_finished_runs_are_terminal():
    assert RUN_TRANSITIONS[RunStatus.DONE] == set() and RUN_TRANSITIONS[RunStatus.ERROR] == set()
