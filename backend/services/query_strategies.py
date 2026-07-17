from abc import ABC, abstractmethod

from llama_index.core import QueryBundle


def _generate_hypothetical(question: str, llm) -> str:
    return str(llm.complete(
        f"Write a short, factual answer to the following question based on your knowledge:"
        f"\n\nQuestion: {question}\n\nAnswer:"
    )).strip()


class QueryStrategy(ABC):
    @abstractmethod
    def build_query(self, question: str, llm) -> object:
        """Returns a str (naive) or QueryBundle (HyDE) for the retriever."""


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


_STRATEGIES = {
    'naive':         NaiveStrategy,
    'hyde_answer':   HyDEAnswerStrategy,
    'hyde_combined': HyDECombinedStrategy,
}


def get_query_strategy(mode: str) -> QueryStrategy:
    return _STRATEGIES.get(mode, NaiveStrategy)()