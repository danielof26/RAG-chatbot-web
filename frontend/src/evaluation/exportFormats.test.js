import { describe, it, expect } from 'vitest'
import { EXPORT_FORMATS, buildExportPayload } from './exportFormats'
import { configTags } from './configSummary'

const run = {
  snapshot_name: 'Prueba 2', language: 'es', n_exec: 1, llm_model: 'gpt-oss:20b', embed_model: 'arctic',
  rag_config: { retrieval_mode: 'router', synthesis_mode: 'compact', similarity_top_k: 5, chunk_size: 512, chunk_overlap: 50,
    temperature: 0.1, rerank: true, rerank_top_n: 3, long_reorder: true },
  results: { global: {}, per_question: [] },
}

describe('exported files', () => {
  const payload = buildExportPayload(run, run)
  it('carry every setting that the history tags show', () => {
    const keys = Object.keys(payload.config)
    for (const tag of configTags(run.rag_config, { llmModel: run.llm_model, embedModel: run.embed_model })) {
      expect(keys).toContain(tag.split(':')[0])
    }
    expect(keys).toEqual(expect.arrayContaining(['configuration', 'language', 'repetitions', 'long_context_reorder', 'indexing', 'chunking']))
  })
  it('write them in csv, json and txt', () => {
    for (const format of Object.values(EXPORT_FORMATS)) {
      const text = format.build(payload)
      expect(text).toContain('long_context_reorder')
      expect(text).toContain('vector store')
    }
  })
})
