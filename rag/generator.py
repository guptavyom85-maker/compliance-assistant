"""Validated JSON provider boundary with one repair attempt and sanitized errors."""
import json
import logging
import time
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


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
            output_limit = settings.LLM_MAX_OUTPUT_TOKENS
            for attempt in range(2):
                try:
                    response = client.chat.completions.create(model=requested_model, temperature=0,
                        max_tokens=output_limit, messages=messages,
                        response_format={'type': 'json_schema', 'json_schema': {
                            'name': schema.__name__.lower(), 'strict': True, 'schema': schema_json}},
                        extra_body={'provider': {'require_parameters': True}})
                except Exception as exc:
                    logger.warning('Structured request failed: model=%s error=%s status=%s',
                                   requested_model, type(exc).__name__, getattr(exc, 'status_code', None))
                    # An authentication error will not improve on another
                    # model, so stop without multiplying the timeout.
                    if getattr(exc, 'status_code', None) in (401, 403):
                        raise GenerationError('Model provider rejected the configured API key or permissions.') from exc
                    break
                if response.usage:
                    usage['input_tokens'] += response.usage.prompt_tokens or 0
                    usage['output_tokens'] += response.usage.completion_tokens or 0
                content = response.choices[0].message.content if response.choices else ''
                finish_reason = response.choices[0].finish_reason if response.choices else 'no_choices'
                if finish_reason == 'length':
                    # Even syntactically valid JSON can be an incomplete answer
                    # when the provider exhausts its output/reasoning budget.
                    # Regenerate from the original request, not truncated JSON.
                    logger.warning('Structured response truncated: model=%s output_limit=%s',
                                   response.model or requested_model, output_limit)
                    retry_limit = min(output_limit * 2, settings.LLM_MAX_RETRY_OUTPUT_TOKENS)
                    if attempt == 0 and retry_limit > output_limit:
                        output_limit = retry_limit
                        messages = list(base_messages)
                        continue
                    break
                # Some reasoning endpoints return only internal reasoning and
                # an empty content field. A repair cannot repair absent output.
                if not content:
                    logger.warning('Structured response empty: model=%s finish=%s',
                                   response.model or requested_model,
                                   finish_reason)
                    break
                try:
                    result = schema.model_validate_json(content)
                    actual_model = response.model or requested_model
                    return result, {'model': actual_model, 'requested_model': requested_model,
                                    'fallback_used': requested_model != model,
                                    **usage, 'latency_ms': round((time.monotonic() - started) * 1000),
                                    'estimated_cost': None}
                except ValueError as exc:
                    # Never log validation inputs or provider bodies: both may
                    # contain private source text. Error codes identify the cause.
                    issues = [item['type'] for item in exc.errors(include_input=False)] if hasattr(exc, 'errors') else [type(exc).__name__]
                    logger.warning('Structured response invalid: model=%s finish=%s issues=%s',
                                   response.model or requested_model, response.choices[0].finish_reason, issues)
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
