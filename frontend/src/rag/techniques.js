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
    if (!selectedTechs.has(t.id)) return
    // Within a "choose one" section the others are not blocked: choosing one replaces the current one
    const sameSection = new Set(s.config_key ? s.techniques.map(x => x.id) : [])
    t.incompat.forEach(id => { if (!sameSection.has(id)) blocked.add(id) })
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
  singleChoiceSections(catalog).forEach(s => {
    const saved = s.techniques.find(t => t.id === cfg[s.config_key])
    techs.add(saved ? saved.id : s.fallback)
  })
  return techs
}

// "Choose one" sections (chunking, ...) are saved as one rag_config value named by the section's config_key:
// the selected technique, or the section's fallback when none is selected.
const singleChoiceSections = (catalog) => catalog.sections.filter(s => s.config_key)

export const computeSectionChoices = (catalog, techs) =>
  Object.fromEntries(singleChoiceSections(catalog).map(s =>
    [s.config_key, s.techniques.find(t => techs.has(t.id))?.id ?? s.fallback]))

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
  const section = catalog.sections.find(s => s.techniques.includes(tech))
  const next = new Set(selectedTechs)
  if (next.has(techId)) {
    if (section.fallback === techId) return selectedTechs     // the fallback can only be left by choosing another
    next.delete(techId)
    if (section.fallback) next.add(section.fallback)          // a "choose one" group never ends up empty
  }
  else { tech.incompat.forEach(id => next.delete(id)); next.add(techId) }
  return next
}
