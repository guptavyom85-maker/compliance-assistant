"""Validated JSON provider boundary with one repair attempt and sanitized errors."""
import json
import time
from django.conf import settings
from openai import OpenAI


class GenerationError(RuntimeError):
    pass


def structured_call(prompt, data, schema, *, judge=False, api_key=None):
    started = time.monotonic()
    key = api_key or settings.OPENROUTER_API_KEY
    model = settings.OPENROUTER_JUDGE_MODEL if judge else settings.OPENROUTER_MODEL
    if not key or not model:
        raise GenerationError('Configure the model and API key before running this operation.')
    client = OpenAI(base_url=settings.OPENROUTER_BASE_URL, api_key=key,
                    timeout=settings.LLM_TIMEOUT_SECONDS, max_retries=0)
    schema_json = schema.model_json_schema()
    base_messages = [dict(role='system', content=prompt + '\nSchema:\n' + json.dumps(schema_json)),
                     dict(role='user', content=json.dumps(data, ensure_ascii=False, default=str))]
    # This router is the last resort when a configured model cannot return
    # schema-constrained output. The actual routed model is still recorded.
    models = tuple(dict.fromkeys((model, *settings.OPENROUTER_FALLBACK_MODELS, 'openrouter/free')))
    usage = {'input_tokens': 0, 'output_tokens': 0}
    try:
        for requested_model in models:
            messages = list(base_messages)
            for attempt in range(2):
                try:
                    response = client.chat.completions.create(model=requested_model, temperature=0,
                        max_tokens=settings.LLM_MAX_OUTPUT_TOKENS, messages=messages,
                        response_format={'type': 'json_schema', 'json_schema': {
                            'name': schema.__name__.lower(), 'strict': True, 'schema': schema_json}},
                        extra_body={'provider': {'require_parameters': True}})
                except Exception as exc:
                    # An authentication error will not improve on another
                    # model, so stop without multiplying the timeout.
                    if getattr(exc, 'status_code', None) in (401, 403):
                        raise GenerationError('Model provider rejected the configured API key or permissions.') from exc
                    break
                if response.usage:
                    usage['input_tokens'] += response.usage.prompt_tokens or 0
                    usage['output_tokens'] += response.usage.completion_tokens or 0
                content = response.choices[0].message.content if response.choices else ''
                # Some reasoning endpoints return only internal reasoning and
                # an empty content field. A repair cannot repair absent output.
                if not content:
                    break
                try:
                    result = schema.model_validate_json(content)
                    actual_model = response.model or requested_model
                    return result, {'model': actual_model, 'requested_model': requested_model,
                                    'fallback_used': requested_model != model,
                                    **usage, 'latency_ms': round((time.monotonic() - started) * 1000),
                                    'estimated_cost': None}
                except ValueError:
                    if attempt == 1:
                        break
                    messages.append(dict(role='assistant', content=content))
                    messages.append(dict(role='user', content='Return the same answer as valid JSON matching the schema.'))
        raise GenerationError('No available model returned valid structured output. Retry or configure a structured-output-capable model.')
    except GenerationError:
        raise
    except Exception as exc:
        # Do not expose provider bodies, keys, or submitted document text.
        raise GenerationError('Model provider unavailable. Please retry later.') from exc
    finally:
        client.close()
