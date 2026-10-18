// One readable summary of a saved configuration (a snapshot or the config an evaluation ran with).
// Shared by the tags in the Evaluation tab and by the downloaded files, so they always list the same things.
// Optional settings only appear when active; `true` flags are shown by name only.
// Conversational memory is left out on purpose: evaluations ask each question on its own, so it has no effect.

// Not stored in rag_config: they have a single implementation today (the other options are still "soon").
const INDEXING = 'vector store'
const CHUNKING = 'fixed-size'

export const configEntries = (cfg = {}, { llmModel, embedModel } = {}) => [
  ['indexing', INDEXING],
  ['chunking', CHUNKING],
  cfg.chunk_size != null && ['chunk', `${cfg.chunk_size}/${cfg.chunk_overlap ?? 0}`],
  ['retrieval', cfg.retrieval_mode],
  cfg.retrieval_mode === 'fusion' && cfg.fusion_num_queries != null && ['fusion_queries', cfg.fusion_num_queries],
  ['top_k', cfg.similarity_top_k],
  cfg.sim_filter && ['sim_filter', cfg.similarity_cutoff ?? true],
  cfg.rerank && ['rerank', true],
  cfg.rerank && cfg.rerank_top_n != null && ['rerank_top_n', cfg.rerank_top_n],
  cfg.xai && ['xai', true],
  cfg.long_reorder && ['long_context_reorder', true],
  ['synthesis', cfg.synthesis_mode],
  ['temp', cfg.temperature],
  ['model', llmModel],
  ['embed_model', embedModel],
].filter(entry => entry && entry[1] != null)

export const configTags = (cfg, models) =>
  configEntries(cfg, models).map(([key, value]) => value === true ? key : `${key}: ${value}`)
