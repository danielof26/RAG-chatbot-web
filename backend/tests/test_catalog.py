"""Invariants of the Advanced-tab catalog (rag_catalog.py): the locks must match what the backend really does."""
import itertools

import pytest

from rag_catalog import get_catalog

CATALOG = get_catalog()
TECHS = {t['id']: t for s in CATALOG['sections'] for t in s['techniques']}
RETRIEVAL_TECHS = [m for m in CATALOG['mode_priority'] if m != 'naive']   # naive is a no-op baseline
NON_COMPACT_SYNTHESIS = ['refine', 'tree_summarize', 'simple_summarize', 'accumulate']
# Engines that build their own synthesis and ignore synthesis_mode (the rest are covered by test_synthesis_modes.py)
SELF_MANAGED_SYNTHESIS = ['crag', 'router']


def locked(a, b):
    return b in TECHS[a]['incompat']


def test_incompatibilities_are_symmetric_and_reference_real_techniques():
    for tech in TECHS.values():
        for other in tech['incompat']:
            assert other in TECHS, f"{tech['id']} references unknown technique {other}"
            assert tech['id'] in TECHS[other]['incompat'], f"{tech['id']} -> {other} is not symmetric"
            assert other != tech['id']


@pytest.mark.parametrize('a,b', list(itertools.combinations(RETRIEVAL_TECHS, 2)))
def test_two_retrieval_techniques_are_never_selectable_together(a, b):
    # Saving keeps only the first one in MODE_PRIORITY, so allowing both would drop one silently.
    assert locked(a, b), f'{a} + {b} would be saved as a single mode and lose one of them'


@pytest.mark.parametrize('tech', SELF_MANAGED_SYNTHESIS)
@pytest.mark.parametrize('synthesis', NON_COMPACT_SYNTHESIS)
def test_engines_that_ignore_synthesis_lock_the_other_modes(tech, synthesis):
    assert locked(tech, synthesis)


@pytest.mark.parametrize('tech', ['fusion', 'bm25'])
def test_similarity_filter_is_locked_for_non_cosine_scores(tech):
    assert locked('sim_filter', tech)


def test_reranking_still_combines_with_crag_and_the_other_postprocessors():
    for other in ('crag', 'sim_filter', 'long_reorder'):
        assert not locked('rerank_ce', other)
    assert locked('rerank_ce', 'rerank_llm')


def test_every_implemented_retrieval_technique_has_a_mode_entry():
    for tech in RETRIEVAL_TECHS:
        assert TECHS[tech]['impl'], tech
        assert tech in CATALOG['mode_techs']
