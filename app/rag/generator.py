"""

LLM answer generation with facts-only constraints (Phase 5).



Uses Groq when ``GROQ_API_KEY`` is set; otherwise a deterministic template

from retrieved chunks (CI/tests without API billing).

"""



from __future__ import annotations



import logging

import re

from dataclasses import dataclass



from app.config import get_settings

from app.rag.retriever import RetrievalResult, document_to_content

from ingestion.index import RetrievedChunk



logger = logging.getLogger(__name__)



SYSTEM_PROMPT = """You are a facts-only assistant for five HDFC mutual fund schemes on Groww.



Rules (non-negotiable):

1. Answer ONLY using facts in [CONTEXT]. If missing, say it is not in the corpus.

2. Maximum 3 sentences total.

3. Include exactly ONE markdown link to the scheme source_url from context, e.g. [scheme page](url).

4. Do not give investment advice, rankings, recommendations, or return comparisons.

5. For fund managers: biographical facts only (name, tenure, education, experience) — no opinions.

6. Do not invent numbers or metrics not present in context.

7. End with a separate line: Last updated from sources: {last_updated}

"""



_MAX_MESSAGE_CHARS = 4096





class GenerationError(Exception):

    """Raised when the LLM cannot produce an answer."""





@dataclass(frozen=True)

class GenerationResult:

    """Raw model output before validation fixes."""



    answer: str

    citation_url: str

    footer: str

    used_template: bool





def format_footer(last_updated: str | None) -> str:

    label = (last_updated or "").strip() or "unknown"

    return f"Last updated from sources: {label}"





def _first_fact_sentence(content: str, max_chars: int = 220) -> str:

    """Extract a short factual line from chunk content for template answers."""

    text = re.sub(r"\s+", " ", content.strip())

    if not text:

        return "See the linked scheme page for details."

    for sep in (". ", "? ", "! "):

        if sep in text:

            candidate = text.split(sep)[0].strip() + "."

            if len(candidate) <= max_chars:

                return candidate

    if len(text) <= max_chars:

        return text if text.endswith(".") else text + "."

    trimmed = text[:max_chars].rsplit(" ", 1)[0]

    return trimmed + "."





def template_generate(

    query: str,

    retrieval: RetrievalResult,

) -> GenerationResult:

    """Deterministic answer from top retrieved chunk (no API key)."""

    if not retrieval.chunks or not retrieval.citation_url:

        raise GenerationError("no chunks for template generation")



    top: RetrievedChunk = retrieval.chunks[0]

    content = document_to_content(top)

    fact = _first_fact_sentence(content)

    url = retrieval.citation_url

    scheme = top.scheme_name

    footer = format_footer(retrieval.last_updated or top.last_updated)



    answer = (

        f"For {scheme}, the corpus states: {fact} "

        f"See the [scheme page]({url})."

    )

    return GenerationResult(

        answer=answer,

        citation_url=url,

        footer=footer,

        used_template=True,

    )





def _groq_generate(query: str, context: str, *, last_updated: str) -> str:

    settings = get_settings()

    if not settings.groq_api_key:

        raise GenerationError("GROQ_API_KEY is not configured")



    from groq import Groq



    client = Groq(api_key=settings.groq_api_key)

    system = SYSTEM_PROMPT.format(last_updated=last_updated or "unknown")

    user = f"{context}\n\n[USER QUESTION]\n{query.strip()}"



    try:

        response = client.chat.completions.create(

            model=settings.chat_model,

            messages=[

                {"role": "system", "content": system},

                {"role": "user", "content": user[:_MAX_MESSAGE_CHARS]},

            ],

            temperature=0.2,

            max_tokens=220,

        )

    except Exception as exc:

        logger.exception("Groq chat completion failed")

        raise GenerationError(str(exc)) from exc



    choice = response.choices[0].message.content if response.choices else None

    if not choice or not choice.strip():

        raise GenerationError("empty LLM response")

    return choice.strip()





def generate_answer(

    query: str,

    retrieval: RetrievalResult,

    *,

    force_template: bool = False,

) -> GenerationResult:

    """

    Produce a draft answer with citation URL and footer metadata.



    Uses template fallback when ``force_template`` or no API key.

    """

    if not retrieval.found or not retrieval.chunks:

        raise GenerationError("retrieval empty")



    citation_url = retrieval.citation_url or retrieval.chunks[0].source_url

    last_updated = retrieval.last_updated or retrieval.chunks[0].last_updated

    footer = format_footer(last_updated)

    settings = get_settings()



    use_template = force_template or not settings.groq_api_key

    if use_template:

        return template_generate(query, retrieval)



    try:

        draft = _groq_generate(

            query,

            retrieval.context,

            last_updated=last_updated or "unknown",

        )

    except GenerationError:

        raise

    except Exception as exc:

        logger.warning("LLM failed, using template fallback: %s", exc)

        return template_generate(query, retrieval)



    return GenerationResult(

        answer=draft,

        citation_url=citation_url,

        footer=footer,

        used_template=False,

    )


