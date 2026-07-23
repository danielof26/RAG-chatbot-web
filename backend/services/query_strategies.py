from abc import ABC, abstractmethod

from llama_index.core import QueryBundle


def _generate_hypothetical(question: str, llm) -> str:
    return str(llm.complete(
        f"Write a short, factual answer to the following question based on your knowledge:"
        f"\n\nQuestion: {question}\n\nAnswer:"
    )).strip()


class _CRAGResponse:
    """Minimal response wrapper so CRAG output is compatible with _write_xai_trace."""
    def __init__(self, nodes):
        self.source_nodes = nodes


class QueryStrategy(ABC):
    @abstractmethod
    def build_query(self, question: str, llm) -> object:
        """Returns a str (naive) or QueryBundle (HyDE) for the retriever."""

    def execute(self, query_engine, question: str, llm, synthesis_question: str = None) -> tuple:
        synthesis_question = synthesis_question or question
        query = self.build_query(question, llm)
        if isinstance(query, QueryBundle):
            query = QueryBundle(query_str=synthesis_question, custom_embedding_strs=query.custom_embedding_strs)
        else:
            query = synthesis_question
        response = query_engine.query(query)
        answer = str(response).strip().replace('\n', ' ').replace(';', ',')
        return answer, response


class NaiveStrategy(QueryStrategy):
    def build_query(self, question: str, llm) -> str:
        return question


class HyDEAnswerStrategy(QueryStrategy):
    def build_query(self, question: str, llm) -> QueryBundle:
        hypothetical = _generate_hypothetical(question, llm)
        return QueryBundle(query_str=question, custom_embedding_strs=[hypothetical])


class HyDECombinedStrategy(QueryStrategy):
    def build_query(self, question: str, llm) -> QueryBundle:
        hypothetical = _generate_hypothetical(question, llm)
        return QueryBundle(query_str=question, custom_embedding_strs=[question, hypothetical])


class CRAGStrategy(QueryStrategy):
    def build_query(self, question: str, llm) -> str:
        return question  # unused — execute() is fully overridden

    def execute(self, query_engine, question: str, llm, synthesis_question: str = None) -> tuple:
        synthesis_question = synthesis_question or question

        nodes = query_engine.retriever.retrieve(question)

        relevant = [n for n in nodes if self._grade(n.text, question, llm) != 'IRRELEVANT']
        if not relevant:
            relevant = nodes  # fallback: use everything if nothing passed

        chunks = "\n---\n".join(n.text for n in relevant)
        prompt = f"Context:\n{chunks}\n\nQuestion: {synthesis_question}\n\nAnswer:"
        answer = str(llm.complete(prompt)).strip().replace('\n', ' ').replace(';', ',')
        return answer, _CRAGResponse(relevant)

    def _grade(self, chunk: str, question: str, llm) -> str:
        prompt = (
            f"Is the following text relevant to answer the question?\n\n"
            f"Question: {question}\n\nText: {chunk}\n\n"
            f"Reply with exactly one word: RELEVANT, AMBIGUOUS, or IRRELEVANT."
        )
        grade = str(llm.complete(prompt)).strip().upper()
        if 'IRRELEVANT' in grade:
            return 'IRRELEVANT'
        if 'RELEVANT' in grade:
            return 'RELEVANT'
        return 'AMBIGUOUS'


_STRATEGIES = {
    'naive':         NaiveStrategy,
    'hyde_answer':   HyDEAnswerStrategy,
    'hyde_combined': HyDECombinedStrategy,
    'crag':          CRAGStrategy,
}


def get_query_strategy(mode: str) -> QueryStrategy:
    return _STRATEGIES.get(mode, NaiveStrategy)()
