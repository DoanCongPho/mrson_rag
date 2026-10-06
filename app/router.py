from typing import Literal

from pydantic import BaseModel

from app.llm import client
from app.tracing import tracer_provider
from openinference.semconv.trace import SpanAttributes

tracer = tracer_provider.get_tracer(__name__)

MIN_TOP_K = 3
MAX_TOP_K = 10
DEFAULT_TOP_K = 5

ROLE_INSTRUCTIONS = """You are the router for an IELTS Speaking assistant chatbot. Your job is NOT to answer the user's question -- it is to classify the question so the system knows whether it needs to search the knowledge base (retrieval), which category to search, and how many document chunks to fetch."""

# Only needed while a single chatbot serves all 3 categories from one vector store.
# If this ever splits into 3 separate sub-chatbots (one per category), each sub-bot's
# router can drop this block entirely and skip the `category` field on RouteDecision.
CATEGORY_INSTRUCTIONS = """There are 4 possible category values:
- "part2": IELTS Speaking Part 2 track (storytelling / cue card). Characteristic vocabulary: TIME, HOW, WHY, VALUE line. Content: cue cards, story expansion, storytelling "tricks", topic practice, pressure simulation.
- "part3": IELTS Speaking Part 3 track (discussion / giving opinions). Characteristic vocabulary: POSITION, REASON, REALITY, VALUE line. Content: Part 3 question types (comparison, prediction, explanation, contrast...), giving deeper answers.
- "writing": Grammar and other content not related to Speaking (relative clauses, adverbial clauses, and other Writing-related material if any).
- "all": Use when the question is general, doesn't clearly belong to Part 2 or Part 3 alone, or the user wants to compare/combine both tracks."""

RETRIEVE_DECISION_INSTRUCTIONS = """Deciding should_retrieve:
- false ONLY if: greetings (hi, hello), thanks, farewells, questions about the chatbot itself (who are you, what can you do), or small talk with zero learning content.
- true for ANY question related to Speaking Part 2, Part 3, or grammar content in the materials -- even if not 100% certain, prefer retrieving over skipping.
- Short definition-style questions ("X là gì?", "X nghĩa là gì?") about a single term are ALWAYS true, even with no extra context and even if the term looks like a generic English word (e.g. "keyword", "chunk") -- this class gives its own vocabulary specific meanings, so brevity or an ordinary-looking word is never a reason to classify as false. When in doubt about a term, retrieving and finding nothing is far better than blocking a real question."""

TOP_K_INSTRUCTIONS = """Deciding top_k (number of document chunks to fetch, range 3-10):
- Narrow, specific questions (e.g. definition of one term, one specific technique) -> low top_k (3-4).
- Broad questions needing synthesis across multiple sections (e.g. "summarize all the steps", "compare everything") -> high top_k (7-10).
- Uncertain -> top_k = 5."""

STANDALONE_QUERY_INSTRUCTIONS = """Deciding standalone_query (the text used to search the materials):
- The user message may include the conversation so far and a summary, followed by the NEW question. Classify the NEW question, using the conversation only as context.
- Rewrite the NEW question into a self-contained question in the same language, so it can be searched without the conversation: replace references like "ý 2", "cái đó", "nó", "ví dụ khác", "giải thích thêm" with the concrete topic they refer to.
- Use the terminology of the course materials when the learner uses a looser name for the same concept (e.g. adverbial clauses are called "mệnh đề trạng ngữ" in the materials, even if the learner writes "mệnh đề trạng từ").
- Do not answer the question and do not add new topics. If it is already self-contained, return it unchanged.
- A follow-up about learning content ("cho ví dụ", "giải thích thêm ý 2") is a real question: should_retrieve = true."""

FALLBACK_INSTRUCTIONS = """If should_retrieve = false, the category and top_k values don't matter -- just fill in "all" and 5."""

ROUTER_SYSTEM_PROMPT = "\n\n".join([
    ROLE_INSTRUCTIONS,
    CATEGORY_INSTRUCTIONS,
    RETRIEVE_DECISION_INSTRUCTIONS,
    TOP_K_INSTRUCTIONS,
    STANDALONE_QUERY_INSTRUCTIONS,
    FALLBACK_INSTRUCTIONS,
])


class RouteDecision(BaseModel):
    should_retrieve: bool
    category: Literal["part2", "part3", "writing", "all"]
    top_k: int
    standalone_query: str


def _router_input(query: str, history_text: str, summary: str | None) -> str:
    if not history_text and not summary:
        return query
    parts = []
    if summary:
        parts.append(f"Summary of earlier conversation:\n{summary}")
    if history_text:
        parts.append(f"Recent conversation:\n{history_text}")
    parts.append(f"NEW question:\n{query}")
    return "\n\n".join(parts)


def route(query: str, history_text: str = "", summary: str | None = None) -> RouteDecision:
    default = RouteDecision(should_retrieve=True, category="all", top_k=DEFAULT_TOP_K, standalone_query=query)
    with tracer.start_as_current_span("route") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
        span.set_attribute(SpanAttributes.INPUT_VALUE, query)

        try:
            completion = client.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": _router_input(query, history_text, summary)},
                ],
                response_format=RouteDecision,
                temperature=0,
            )
            decision = completion.choices[0].message.parsed
            if decision is None:
                raise ValueError("router returned no parsed output (refusal or empty)")
        except Exception:
            span.set_attribute("route.fallback", True)
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, default.model_dump_json())
            return default

        clamped_top_k = max(MIN_TOP_K, min(MAX_TOP_K, decision.top_k))
        standalone_query = decision.standalone_query.strip() or query
        decision = decision.model_copy(update={"top_k": clamped_top_k, "standalone_query": standalone_query})
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, decision.model_dump_json())
        return decision
