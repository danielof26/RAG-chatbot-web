import { describe, expect, it } from 'vitest'
import {
  EMPTY_CATALOG, blockedTechsFor, computeRetrievalMode, computeSectionChoices, computeSynthesisMode, initTechsFromMode,
  techsFromRagConfig, toggleTechSet,
} from './techniques'

// A small catalog with the same shape the backend serves (backend/rag_catalog.py)
const tech = (id, incompat = []) => ({ id, incompat })
const catalog = {
  sections: [{ techniques: [
    tech('naive'), tech('crag', ['refine']), tech('bm25', ['crag']),
    tech('compact'), tech('refine', ['crag']),
    tech('sim_filter'), tech('rerank_ce'), tech('xai'), tech('long_reorder'),
  ] }],
  default_techs: ['vector_index'],
  mode_techs: { naive: ['naive'], crag: ['crag'], bm25: ['bm25'] },
  mode_priority: ['bm25', 'crag', 'naive'],
  synthesis_priority: ['refine', 'compact'],
}

describe('techsFromRagConfig', () => {
  it('returns nothing before the catalog has loaded', () => {
    expect(techsFromRagConfig(null, { retrieval_mode: 'crag' }).size).toBe(0)
  })

  it('falls back to naive + compact for an empty or missing config', () => {
    for (const cfg of [undefined, null, {}]) {
      const techs = techsFromRagConfig(catalog, cfg)
      expect(techs.has('naive')).toBe(true)
      expect(techs.has('vector_index')).toBe(true)
    }
  })

  it('selects the mode and the on/off flags', () => {
    const techs = techsFromRagConfig(catalog, { retrieval_mode: 'bm25', sim_filter: true, rerank: true, xai: true, long_reorder: true })
    expect([...techs]).toEqual(expect.arrayContaining(['bm25', 'sim_filter', 'rerank_ce', 'xai', 'long_reorder']))
  })

  it('selects a non-default synthesis mode', () => {
    const techs = techsFromRagConfig(catalog, { synthesis_mode: 'refine' })
    expect(techs.has('refine')).toBe(true)
    expect(techs.has('compact')).toBe(false)
  })

  it('drops a saved synthesis mode that the retrieval mode forbids, keeping compact', () => {
    const techs = techsFromRagConfig(catalog, { retrieval_mode: 'crag', synthesis_mode: 'refine' })
    expect(techs.has('crag')).toBe(true)
    expect(techs.has('refine')).toBe(false)
    expect(techs.has('compact')).toBe(true)
  })

  it('does not mutate the catalog defaults', () => {
    techsFromRagConfig(catalog, { retrieval_mode: 'crag', xai: true })
    expect(catalog.default_techs).toEqual(['vector_index'])
  })
})

describe('mode helpers', () => {
  it('initTechsFromMode treats an unknown mode as naive', () => {
    expect(initTechsFromMode(catalog, 'magic').has('naive')).toBe(true)
  })

  it('blockedTechsFor lists what the selected techniques forbid', () => {
    expect(blockedTechsFor(catalog, new Set(['crag']))).toEqual(new Set(['refine']))
    expect(blockedTechsFor(catalog, new Set()).size).toBe(0)
  })

  it('computeRetrievalMode picks the highest-priority selected mode', () => {
    expect(computeRetrievalMode(catalog, new Set(['naive', 'bm25']))).toBe('bm25')
    expect(computeRetrievalMode(catalog, new Set(['sim_filter']))).toBe('naive')
  })

  it('computeSynthesisMode defaults to compact', () => {
    expect(computeSynthesisMode(catalog, new Set(['refine']))).toBe('refine')
    expect(computeSynthesisMode(catalog, new Set())).toBe('compact')
  })

  it('an empty catalog does not crash and falls back to naive', () => {
    expect([...techsFromRagConfig(EMPTY_CATALOG, {})]).toEqual(['naive'])
  })
})

// A "choose one" section (chunking): saved under its config_key, falling back to its default
describe('single-choice sections', () => {
  const chunkCatalog = {
    ...catalog,
    sections: [
      ...catalog.sections,
      { id: 'chunk', config_key: 'chunk_strategy', fallback: 'fixed', techniques: [
        { id: 'fixed', impl: true, incompat: ['window'] },
        { id: 'window', impl: true, incompat: ['fixed'] },
        { id: 'soon', impl: false, incompat: [] },
      ] },
    ],
  }

  it('selects the saved choice, or the fallback when there is none or it is unknown', () => {
    expect(techsFromRagConfig(chunkCatalog, { chunk_strategy: 'window' }).has('window')).toBe(true)
    expect(techsFromRagConfig(chunkCatalog, { chunk_strategy: 'window' }).has('fixed')).toBe(false)
    for (const cfg of [{}, { chunk_strategy: 'gone' }]) {
      expect(techsFromRagConfig(chunkCatalog, cfg).has('fixed')).toBe(true)
    }
  })

  it('computeSectionChoices reads the selection back, and the fallback when nothing is selected', () => {
    expect(computeSectionChoices(chunkCatalog, new Set(['window']))).toEqual({ chunk_strategy: 'window' })
    expect(computeSectionChoices(chunkCatalog, new Set())).toEqual({ chunk_strategy: 'fixed' })
    expect(computeSectionChoices(catalog, new Set(['window']))).toEqual({})
  })

  it('does not lock the other choices of the section, but still locks what the selected one forbids elsewhere', () => {
    const cat = { ...chunkCatalog, sections: [chunkCatalog.sections[0],
      { ...chunkCatalog.sections[1], techniques: [
        { id: 'fixed', impl: true, incompat: ['window', 'crag'] }, { id: 'window', impl: true, incompat: ['fixed'] }] }] }
    expect(blockedTechsFor(cat, new Set(['fixed']))).toEqual(new Set(['crag']))
  })

  it('choosing another replaces the current one, and unchoosing it goes back to the fallback', () => {
    const fixed = new Set(['naive', 'fixed'])
    const window = toggleTechSet(chunkCatalog, fixed, 'window')
    expect([...window].sort()).toEqual(['naive', 'window'])
    expect([...toggleTechSet(chunkCatalog, window, 'window')].sort()).toEqual(['fixed', 'naive'])
  })

  it('clicking the selected fallback, or a technique that is not implemented, changes nothing', () => {
    const fixed = new Set(['naive', 'fixed'])
    expect(toggleTechSet(chunkCatalog, fixed, 'fixed')).toBe(fixed)
    expect(toggleTechSet(chunkCatalog, fixed, 'soon')).toBe(fixed)
  })
})
