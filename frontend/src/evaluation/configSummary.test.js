import { describe, it, expect } from 'vitest'
import { configTags } from './configSummary'

describe('configTags', () => {
  it('lists every selected setting, including the fixed indexing and chunking', () => {
    const cfg = {
      retrieval_mode: 'router', synthesis_mode: 'compact', similarity_top_k: 5, chunk_size: 512, chunk_overlap: 50,
      temperature: 0.1, rerank: true, rerank_top_n: 3, long_reorder: true, conv_memory: true,
    }
    expect(configTags(cfg, { llmModel: 'gpt-oss:20b', embedModel: 'arctic' })).toEqual([
      'indexing: vector store', 'chunking: fixed-size', 'chunk: 512/50', 'retrieval: router', 'top_k: 5',
      'rerank', 'rerank_top_n: 3', 'long_context_reorder', 'synthesis: compact', 'temp: 0.1',
      'model: gpt-oss:20b', 'embed_model: arctic',
    ])
  })

  it('leaves out what is off', () => {
    const tags = configTags({ retrieval_mode: 'naive', rerank: false, sim_filter: false, xai: false })
    expect(tags).toEqual(['indexing: vector store', 'chunking: fixed-size', 'retrieval: naive'])
  })
})
