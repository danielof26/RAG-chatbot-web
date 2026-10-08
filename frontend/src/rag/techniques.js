// Pure helpers over the technique catalog served by GET /api/rag/techniques.
// The catalog (sections, defaults, mode tables, incompatibilities) lives in the backend: backend/rag_catalog.py.

export const EMPTY_CATALOG = {
  sections: [], default_techs: [], mode_techs: {}, mode_priority: [], synthesis_priority: []
}

export const initTechsFromMode = (catalog, mode) => {
  const t = new Set(catalog.default_techs)
  ;(catalog.mode_techs[mode] ?? ['naive']).forEach(id => t.add(id))
  return t
}

// Techniques that can't be picked because an already selected one is incompatible with them
export const blockedTechsFor = (catalog, selectedTechs) => {
  const blocked = new Set()
  catalog.sections.forEach(s => s.techniques.forEach(t => {
    if (selectedTechs.has(t.id)) t.incompat.forEach(id => blocked.add(id))
  }))
  return blocked
}

// Pills selected for an agent, from its saved rag_config (mode + synthesis mode + the on/off flags).
// The mode is authoritative; a saved extra that a lock now forbids next to it (e.g. a synthesis mode that
// the mode ignores) is left out instead of showing a combination the UI would never let you build.
export const techsFromRagConfig = (catalog, ragConfig) => {
  if (!catalog) return new Set()
  const cfg = ragConfig ?? {}
  const techs = initTechsFromMode(catalog, cfg.retrieval_mode ?? 'naive')
  const addIfAllowed = (id) => { if (!blockedTechsFor(catalog, techs).has(id)) techs.add(id) }
  const synthMode = cfg.synthesis_mode ?? 'compact'
  if (synthMode !== 'compact') { techs.delete('compact'); addIfAllowed(synthMode); if (!techs.has(synthMode)) techs.add('compact') }
  if (cfg.sim_filter)   addIfAllowed('sim_filter')
  if (cfg.rerank)       addIfAllowed('rerank_ce')
  if (cfg.xai)          addIfAllowed('xai')
  if (cfg.long_reorder) addIfAllowed('long_reorder')
  return techs
}

export const computeRetrievalMode = (catalog, techs) =>
  catalog.mode_priority.find(mode => techs.has(mode)) ?? 'naive'

export const computeSynthesisMode = (catalog, techs) =>
  catalog.synthesis_priority.find(mode => techs.has(mode)) ?? 'compact'

export const findTech = (catalog, techId) => {
  for (const s of catalog.sections) {
    const found = s.techniques.find(t => t.id === techId)
    if (found) return found
  }
  return null
}

// Returns the new selection, or the same Set instance when the click does nothing
export const toggleTechSet = (catalog, selectedTechs, techId) => {
  if (catalog.default_techs.includes(techId)) return selectedTechs
  const tech = findTech(catalog, techId)
  if (!tech?.impl) return selectedTechs
  const next = new Set(selectedTechs)
  if (next.has(techId)) { next.delete(techId) }
  else { tech.incompat.forEach(id => next.delete(id)); next.add(techId) }
  return next
}
