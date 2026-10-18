// Builds the downloadable files of an evaluation run. Each format turns the same
// payload ({ config, global, perQuestion }) into text; adding a format = adding one entry.

import { configEntries } from './configSummary'

const csvCell = (value) => `"${String(value ?? '').replace(/"/g, '""')}"`

// Same summary as the tags shown for a saved configuration, plus what only the run knows.
const summarizeConfig = (run) => Object.fromEntries([
  ['configuration', run.snapshot_name],
  ...configEntries(run.rag_config ?? {}, { llmModel: run.llm_model, embedModel: run.embed_model }),
  ['language', run.language],
  ['repetitions', run.n_exec],
].filter(entry => entry[1] != null))

export const buildExportPayload = (run, detail) => ({
  config: summarizeConfig(detail),
  global: detail.results?.global ?? null,
  perQuestion: detail.results?.per_question ?? [],
})

const toCSV = ({ config, perQuestion }) => '\uFEFF' + [
  ...Object.entries(config).map(([k, v]) => `# ${k};${v ?? ''}`),
  '',
  'Question;answer;Binary;Quality;BERT',
  ...perQuestion.map(pq => [
    csvCell(pq.question),
    csvCell(pq.last_answer),
    pq.score?.mean ?? '',
    pq.rouge1_mean ?? '',
    pq.bertscore_mean ?? '',
  ].join(';')),
].join('\n')

const toJSON = ({ config, global, perQuestion }) =>
  JSON.stringify({ config, global, per_question: perQuestion }, null, 2)

const toTXT = ({ config, global, perQuestion }) => [
  'CONFIGURATION',
  ...Object.entries(config).map(([k, v]) => `${k}: ${v ?? '-'}`),
  '',
  'GLOBAL RESULTS',
  ...Object.entries(global ?? {}).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`),
  '',
  'PER QUESTION',
  ...perQuestion.flatMap((pq, i) => [
    `Q${i + 1}: ${pq.question}`,
    `Answer: ${pq.last_answer}`,
    `Binary: ${pq.score?.mean ?? '-'} | Quality: ${pq.rouge1_mean ?? '-'} | BERT: ${pq.bertscore_mean ?? '-'}`,
    '',
  ]),
].join('\n')

export const EXPORT_FORMATS = {
  csv:  { label: 'CSV',  mime: 'text/csv;charset=utf-8;',         build: toCSV },
  json: { label: 'JSON', mime: 'application/json;charset=utf-8;', build: toJSON },
  txt:  { label: 'TXT',  mime: 'text/plain;charset=utf-8;',       build: toTXT },
}

// Browsers throttle downloads fired back-to-back, so they are spaced out.
const DOWNLOAD_GAP_MS = 400
const pause = (ms) => new Promise(resolve => setTimeout(resolve, ms))

export const downloadRun = async (run, detail, formatKeys) => {
  const payload = buildExportPayload(run, detail)
  const baseName = `eval_${run.snapshot_name.replace(/\s+/g, '_')}_${run._id.slice(-6)}`
  for (const [i, key] of formatKeys.entries()) {
    if (i > 0) await pause(DOWNLOAD_GAP_MS)
    const { mime, build } = EXPORT_FORMATS[key]
    const url = URL.createObjectURL(new Blob([build(payload)], { type: mime }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${baseName}.${key}`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  }
}
