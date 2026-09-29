import os

from openai import OpenAI
from openai import APIStatusError

# Free OpenRouter models can be removed or temporarily rate-limited. Prefer the
# configured model, then try the currently known fallbacks for 404/429 errors.
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "liquid/lfm-2.5-2.6b:free")
FALLBACK_MODELS = (
    "qwen/qwen3.8-27b:free",
    "google/gemma-4-31b-it:free",
)

NOT_FOUND_MSG = "This information is not found in the loaded documents."


def generate_answer(question: str, context_chunks: list[dict], api_key: str | None = None) -> str:
    if not context_chunks:
        return NOT_FOUND_MSG

    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return "Error generating answer: OPENROUTER_API_KEY is not set."

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=60.0,
        max_retries=1,
    )

    context_text = ""
    for chunk in context_chunks:
        doc_title = chunk.get("document_title", "Unknown Document")
        para_id = chunk.get("paragraph_id", "")
        page_num = chunk.get("page_number", "")
        text = chunk.get("text", "")
        context_text += (
            f"Document: {doc_title}\nParagraph: {para_id}\n"
            f"Page: {page_num}\nContent: {text}\n\n"
        )

    system_prompt = (
        "You are an expert regulatory compliance assistant. Answer the user's question ONLY using the provided context. "
        "For every claim you make, you MUST cite the relevant paragraph number and page number from the context.\n"
        f"If the provided context does not contain the answer, you must output EXACTLY: '{NOT_FOUND_MSG}'\n"
        "Include the following disclaimer at the end of your answer: "
        "'Disclaimer: This answer is provided for informational purposes only and does not constitute legal advice.'"
    )

    user_prompt = f"Context chunks:\n{context_text}\n\nQuestion:\n{question}"

    models = tuple(dict.fromkeys((DEFAULT_MODEL, *FALLBACK_MODELS)))
    last_error = None

    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            # content can be None or empty if the provider returned nothing usable
            content = response.choices[0].message.content if response.choices else None
            return content or "Error generating answer: model returned no text."
        except APIStatusError as exc:
            last_error = exc
            if exc.status_code not in (404, 429):
                break
        except Exception as exc:
            last_error = exc
            break

    return f"Error generating answer: {last_error}"
