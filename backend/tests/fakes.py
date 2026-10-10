"""Deterministic stand-ins for the language and embedding models, good enough to drive every RAG architecture.

ScriptedLLM answers each kind of prompt the pipeline can send (CRAG grading, Self-RAG critique, router choice,
sub-question generation, HyDE, RAPTOR summary, ...) in the exact format LlamaIndex expects, and records every
call, so a test can state which model calls an architecture makes. HashEmbedding is a bag-of-words embedding:
texts sharing words are close, so retrieval is meaningful without a real model."""
import hashlib
import json
import re

import numpy as np
from llama_index.core.bridge.pydantic import Field
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.llms import CompletionResponse, CustomLLM, LLMMetadata

EMBED_DIM = 128

# Marker phrases of the prompts the pipeline builds -> a short name for the kind of call
_PROMPT_KINDS = (
    ('Reply with exactly one word: RELEVANT', 'crag_grade'),
    ('Evaluate this answer. Reply with ONLY a JSON', 'selfrag_eval'),
    ('Rewrite the answer fixing the problems', 'selfrag_rewrite'),
    ('Write a short, factual answer', 'hyde'),
    ('Using only the choices above', 'router_select'),
    ('output a list of relevant sub-questions', 'subq_gen'),
    ('Summarize the provided text', 'raptor_summary'),
    ('Answer the question using ONLY these fragments', 'xai_refine'),
    ('Context:\n', 'crag_answer'),        # CRAG: "Context:\n<chunks>\n\nQuestion: ..."; LlamaIndex says "Context information"
)


class HashEmbedding(BaseEmbedding):
    def _vector(self, text):
        v = np.zeros(EMBED_DIM)
        for word in re.findall(r'[a-z]+', text.lower()):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBED_DIM] += 1
        norm = np.linalg.norm(v)
        return (v / norm if norm else v).tolist()

    def _get_query_embedding(self, query): return self._vector(query)
    def _get_text_embedding(self, text): return self._vector(text)
    async def _aget_query_embedding(self, query): return self._vector(query)


class ScriptedLLM(CustomLLM):
    calls: list = Field(default_factory=list)      # [(kind, prompt)]
    hypothetical: str = 'volcano eruption lava magma crater'
    cite: bool = False                              # answer with a verifiable [Source: ...] citation
    quotes: list = Field(default_factory=list)      # citations already given (see _quote_from_context)
    invent: str = ''                                # answer with a citation that is NOT in the documents

    @property
    def metadata(self):
        return LLMMetadata(context_window=8000, num_output=256, model_name='scripted')

    @staticmethod
    def kind_of(prompt):
        for marker, kind in _PROMPT_KINDS:
            if marker in prompt:
                return kind
        return 'answer'

    def kinds(self):
        return [kind for kind, _ in self.calls]

    def prompts(self, kind):
        return [prompt for k, prompt in self.calls if k == kind]

    def complete(self, prompt, formatted=False, **kwargs):
        kind = self.kind_of(prompt)
        self.calls.append((kind, prompt))
        return CompletionResponse(text=self._reply(kind, prompt))

    def stream_complete(self, prompt, formatted=False, **kwargs):
        yield self.complete(prompt)

    def _quote_from_context(self, prompt):
        """First words of the first retrieved chunk in the prompt: the first line after a context header that
        is neither a "key: value" metadata line nor a separator. Prompts built from earlier answers (the
        sub-question combination step) have no chunk, so they repeat the last quote."""
        lines = [line.strip() for line in prompt.splitlines()]
        for i, line in enumerate(lines):
            if line.startswith(('Context', 'file_path:')):
                for candidate in lines[i + 1:]:
                    if candidate and not candidate.startswith('---') and not re.match(r'\w+: ', candidate):
                        quote = ' '.join(candidate.split()[:6])
                        self.quotes.append(quote)
                        return quote
        if self.quotes:
            return self.quotes[-1]
        raise AssertionError('no retrieved chunk in the prompt to quote')

    def _reply(self, kind, prompt):
        if kind == 'crag_grade':
            question = re.search(r'Question: (.*)\n', prompt).group(1)
            text = prompt.split('Text:', 1)[1].lower()
            return 'RELEVANT' if any(w in text for w in re.findall(r'[a-z]{5,}', question.lower())) else 'IRRELEVANT'
        if kind == 'selfrag_eval':
            return '{"supported": false, "missing_info": "m", "issues": ["i"]}'
        if kind == 'hyde':
            return self.hypothetical
        if kind == 'router_select':
            return json.dumps([{'choice': 1, 'reason': 'simple factual question'}])
        if kind == 'subq_gen':
            return json.dumps({'items': [{'sub_question': 'What is the Eiffel Tower?', 'tool_name': 'query_engine_tool'},
                                         {'sub_question': 'Who designed it?', 'tool_name': 'query_engine_tool'}]})
        if kind == 'raptor_summary':
            return 'condensed overview of the passages'
        if self.invent:
            return f'Yes. [Source: {self.invent}]'
        if self.cite:
            return f'Here is the answer. [Source: {self._quote_from_context(prompt)}]'
        return f'ANS<<{prompt}>>'        # echoes the prompt: the answer shows exactly what the model was given


class FakeProvider:
    """Stands in for services.llm_providers.*Provider in setup_rag()."""

    def __init__(self, llm):
        self.llm = llm

    def build_llm(self, **kwargs):
        return self.llm

    def build_embedding(self, model):
        return HashEmbedding()
