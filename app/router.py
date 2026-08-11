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
- false if: greetings (hi, hello), thanks, farewells, questions about the chatbot itself (who are you, what can you do), or small talk unrelated to IELTS learning content.
- true for ANY question related to Speaking Part 2, Part 3, or grammar content in the materials -- even if not 100% certain, prefer retrieving over skipping."""

TOP_K_INSTRUCTIONS = """Deciding top_k (number of document chunks to fetch, range 3-10):
- Narrow, specific questions (e.g. definition of one term, one specific technique) -> low top_k (3-4).
- Broad questions needing synthesis across multiple sections (e.g. "summarize all the steps", "compare everything") -> high top_k (7-10).
- Uncertain -> top_k = 5."""

FALLBACK_INSTRUCTIONS = """If should_retrieve = false, the category and top_k values don't matter -- just fill in "all" and 5."""

ROUTER_SYSTEM_PROMPT = "\n\n".join([
    ROLE_INSTRUCTIONS,
    CATEGORY_INSTRUCTIONS,
    RETRIEVE_DECISION_INSTRUCTIONS,
    TOP_K_INSTRUCTIONS,
    FALLBACK_INSTRUCTIONS,
])


class RouteDecision(BaseModel):
    should_retrieve: bool
    category: Literal["part2", "part3", "writing", "all"]
    top_k: int


DEFAULT_DECISION = RouteDecision(should_retrieve=True, category="all", top_k=DEFAULT_TOP_K)


def route(query: str) -> RouteDecision:
    with tracer.start_as_current_span("route") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
        span.set_attribute(SpanAttributes.INPUT_VALUE, query)

        try:
            completion = client.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                response_format=RouteDecision,
                temperature=0,
            )
            decision = completion.choices[0].message.parsed
            if decision is None:
                raise ValueError("router returned no parsed output (refusal or empty)")
        except Exception:
            span.set_attribute("route.fallback", True)
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, DEFAULT_DECISION.model_dump_json())
            return DEFAULT_DECISION

        clamped_top_k = max(MIN_TOP_K, min(MAX_TOP_K, decision.top_k))
        decision = decision.model_copy(update={"top_k": clamped_top_k})
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, decision.model_dump_json())
        return decision
