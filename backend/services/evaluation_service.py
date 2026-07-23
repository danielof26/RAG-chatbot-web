import csv
import io
import statistics
import time
from datetime import datetime, timezone

import spacy
from bson import ObjectId
from nltk.stem import SnowballStemmer
from rouge_score import rouge_scorer as rouge_lib

import config
from db import agents_col, config_snapshots_col, evaluation_runs_col, llm_servers_col
from services.llm_providers import OllamaProvider, get_provider
from services.rag_engine import run_rag, setup_rag

_NLP_MODELS = {
    'es': 'es_core_news_sm',
    'en': 'en_core_web_sm',
}
_nlp_cache = {}
_rouge_scorer = rouge_lib.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=False)
_stemmers = {
    'es': SnowballStemmer('spanish'),
    'en': SnowballStemmer('english'),
}


def _get_nlp(language: str):
    if language not in _nlp_cache:
        _nlp_cache[language] = spacy.load(_NLP_MODELS.get(language, _NLP_MODELS['en']))
    return _nlp_cache[language]


def semantics(text: str, nlp) -> list:
    """Returns stemmed lemmas for a given text using spaCy + Snowball stemmer."""
    stemmer = _stemmers.get(nlp.lang, _stemmers['es'])
    doc = nlp(text.lower())
    return [stemmer.stem(token.lemma_) for token in doc]


def validate(rag_answer: str, keys_string: str, nlp) -> float:
    """Scores a RAG answer by checking how many keywords are present after lemmatisation."""
    sem_answer = semantics(rag_answer, nlp)
    key_list = [k.strip() for k in keys_string.split(',') if k.strip()]
    if not key_list:
        return 0.0
    n_found = sum(1 for k in key_list if any(s in sem_answer for s in semantics(k, nlp)))
    return round(n_found / len(key_list), 2)


def compute_rouge(generated: str, reference: str) -> dict:
    """Computes ROUGE-1, ROUGE-2 and ROUGE-L F1 scores between a generated and a reference answer."""
    scores = _rouge_scorer.score(reference, generated)
    return {
        'rouge1': round(scores['rouge1'].fmeasure, 4),
        'rouge2': round(scores['rouge2'].fmeasure, 4),
        'rougeL': round(scores['rougeL'].fmeasure, 4),
    }


def parse_questions_csv(file_bytes: bytes) -> list:
    """Parses an uploaded CSV (Question;Keywords;Answer) into a list of question dicts."""
    text = file_bytes.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text), delimiter=';')
    questions = []
    for row in reader:
        questions.append({
            'question': row['Question'].strip(),
            'keywords': row['Keywords'].strip(),
            'reference_answer': row.get('Answer', '').strip()
        })
    return questions


def _resolve_llm_provider(snapshot: dict):
    server_id = snapshot.get('llm_server_id')
    if not server_id:
        return OllamaProvider(base_url='http://localhost:11434')
    server = llm_servers_col.find_one({'_id': ObjectId(str(server_id))})
    if not server:
        return OllamaProvider(base_url='http://localhost:11434')
    return get_provider(server)


def _resolve_embed_provider(snapshot: dict):
    server_id = snapshot.get('embed_server_id')
    if not server_id:
        raise ValueError('This configuration has no Embedding Server configured.')
    server = llm_servers_col.find_one({'_id': ObjectId(str(server_id))})
    if not server:
        raise ValueError('The Embedding Server saved in this configuration no longer exists.')
    return get_provider(server)


def _aggregate(values: list) -> dict:
    return {
        'mean': round(sum(values) / len(values), 4),
        'min': round(min(values), 4),
        'max': round(max(values), 4),
        'variance': round(statistics.variance(values), 4) if len(values) > 1 else 0.0,
        'std': round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
    }


def _load_run_inputs(run: dict):
    agent = agents_col.find_one({'_id': ObjectId(run['agent_id'])})
    snapshot = config_snapshots_col.find_one({'_id': ObjectId(run['snapshot_id'])})
    if not agent or not snapshot:
        raise ValueError('Agent or configuration snapshot not found.')

    file_paths = [d['file_path'] for d in agent.get('documents', [])]
    if not file_paths:
        raise ValueError('This agent has no documents to evaluate against.')

    return agent, snapshot, file_paths


def _update_progress(run_id: str, progress: dict):
    evaluation_runs_col.update_one({'_id': ObjectId(run_id)}, {'$set': {'progress': progress}})


def _build_query_engine(run_id: str, agent: dict, snapshot: dict, file_paths: list):
    _update_progress(run_id, {'phase': 'indexing'})
    rag_config = snapshot.get('rag_config', {})
    return setup_rag(
        llm_provider=_resolve_llm_provider(snapshot),
        embed_provider=_resolve_embed_provider(snapshot),
        model_name=snapshot.get('llm_model', config.DEFAULT_LLM),
        embed_model=snapshot.get('embed_model', config.DEFAULT_EMBED_MODEL),
        file_paths=file_paths,
        chroma_path=config.CHROMA_PATH,
        chroma_col=f'eval_{run_id}',
        prompt=agent.get('prompt', ''),
        chunk_size=rag_config.get('chunk_size', 512),
        chunk_overlap=rag_config.get('chunk_overlap', 50),
        top_k=rag_config.get('similarity_top_k', 5),
        temperature=rag_config.get('temperature', 0.1)
    )


def _build_per_question_results(questions, scores, hallucinations_all, rouge_scores, last_answers):
    per_question = []
    for i, q in enumerate(questions):
        valid_h = [h for h in hallucinations_all[i] if h >= 0]
        rg_i = rouge_scores[i]
        has_rouge = len(rg_i['rouge1']) > 0
        per_question.append({
            'question': q['question'],
            'keywords': q['keywords'],
            'last_answer': last_answers[i],
            'score': _aggregate(scores[i]),
            'hallucinations_mean': round(sum(valid_h) / len(valid_h), 2) if valid_h else -1,
            'rouge1_mean': round(sum(rg_i['rouge1']) / len(rg_i['rouge1']), 4) if has_rouge else None,
            'rouge2_mean': round(sum(rg_i['rouge2']) / len(rg_i['rouge2']), 4) if has_rouge else None,
            'rougeL_mean': round(sum(rg_i['rougeL']) / len(rg_i['rougeL']), 4) if has_rouge else None,
        })
    return per_question


def _execute_questions(run_id: str, query_engine, llm, run: dict, nlp, retrieval_mode: str = 'naive'):
    questions = run['dataset']
    architecture = 'xai' if run['xai'] else 'naive'
    n_exec = run['n_exec']
    total_steps = len(questions) * n_exec

    scores             = [[] for _ in questions]
    hallucinations_all = [[] for _ in questions]
    rouge_scores       = [{'rouge1': [], 'rouge2': [], 'rougeL': []} for _ in questions]
    last_answers       = [''] * len(questions)

    step = 0
    for exec_num in range(1, n_exec + 1):
        for i, q in enumerate(questions):
            step += 1
            _update_progress(run_id, {
                'phase': 'querying',
                'step': step,
                'total': total_steps,
                'exec_num': exec_num,
                'n_exec': n_exec,
                'question_num': i + 1,
                'n_questions': len(questions),
                'question': q['question']
            })

            (answer, hallucinations), = run_rag(query_engine, [q], architecture=architecture, llm=llm, exec_num=exec_num, retrieval_mode=retrieval_mode)
            scores[i].append(validate(answer, q['keywords'], nlp))
            hallucinations_all[i].append(hallucinations)
            last_answers[i] = answer
            if q['reference_answer']:
                rg = compute_rouge(answer, q['reference_answer'])
                rouge_scores[i]['rouge1'].append(rg['rouge1'])
                rouge_scores[i]['rouge2'].append(rg['rouge2'])
                rouge_scores[i]['rougeL'].append(rg['rougeL'])

    return _build_per_question_results(questions, scores, hallucinations_all, rouge_scores, last_answers)


def _build_global_results(per_question: list, time_seconds: float) -> dict:
    medias_score = [pq['score']['mean'] for pq in per_question]
    all_h = [pq['hallucinations_mean'] for pq in per_question if pq['hallucinations_mean'] >= 0]
    all_r1 = [pq['rouge1_mean'] for pq in per_question if pq['rouge1_mean'] is not None]
    all_r2 = [pq['rouge2_mean'] for pq in per_question if pq['rouge2_mean'] is not None]
    all_rouge_l = [pq['rougeL_mean'] for pq in per_question if pq['rougeL_mean'] is not None]

    return {
        'score': _aggregate(medias_score),
        'avg_hallucinations': round(sum(all_h) / len(all_h), 2) if all_h else -1,
        'avg_rouge1': round(sum(all_r1) / len(all_r1), 4) if all_r1 else None,
        'avg_rouge2': round(sum(all_r2) / len(all_r2), 4) if all_r2 else None,
        'avg_rougeL': round(sum(all_rouge_l) / len(all_rouge_l), 4) if all_rouge_l else None,
        'time_seconds': time_seconds
    }


def _cleanup_eval_collection(run_id: str):
    try:
        import chromadb
        chromadb.PersistentClient(path=config.CHROMA_PATH).delete_collection(f'eval_{run_id}')
    except Exception:
        pass


def run_evaluation(run_id: str):
    """Runs a full evaluation for one config snapshot and stores the result in MongoDB."""
    run = evaluation_runs_col.find_one({'_id': ObjectId(run_id)})
    if not run:
        return

    try:
        agent, snapshot, file_paths = _load_run_inputs(run)
        nlp = _get_nlp(run['language'])
        query_engine, llm = _build_query_engine(run_id, agent, snapshot, file_paths)

        retrieval_mode = snapshot.get('rag_config', {}).get('retrieval_mode', 'naive')
        start_time = time.time()
        per_question = _execute_questions(run_id, query_engine, llm, run, nlp, retrieval_mode)
        time_seconds = round(time.time() - start_time, 2)

        results = {
            'per_question': per_question,
            'global': _build_global_results(per_question, time_seconds)
        }

        evaluation_runs_col.update_one(
            {'_id': ObjectId(run_id)},
            {'$set': {'status': 'done', 'results': results, 'finished_at': datetime.now(timezone.utc)}}
        )
    except Exception as e:
        evaluation_runs_col.update_one(
            {'_id': ObjectId(run_id)},
            {'$set': {'status': 'error', 'error': str(e), 'finished_at': datetime.now(timezone.utc)}}
        )
    finally:
        _cleanup_eval_collection(run_id)