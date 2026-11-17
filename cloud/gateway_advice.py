"""Read-only device projection of existing advice; never grants actuation."""
import json
import math
from urllib.parse import parse_qs

MAX_AGE_MS = 120000


def parse_gateway_query(raw):
    if not raw or len(raw) > 256:
        raise ValueError('invalid gateway query')
    query = parse_qs(raw, keep_blank_values=True, max_num_fields=5)
    keys = {'gateway', 'boot_session', 'request_id', 'cup_session', 'nonce'}
    if set(query) != keys or any(len(values) != 1 for values in query.values()) or query['gateway'] != ['1']:
        raise ValueError('invalid gateway query')
    result = {}
    for key in keys - {'gateway'}:
        value = query[key][0]
        if not value.isascii() or not value.isdecimal() or not 1 <= len(value) <= 10 or not 1 <= int(value) <= 4294967295 or str(int(value)) != value:
            raise ValueError('invalid gateway identifier')
        result[key] = int(value)
    return result


def project_advice(row, context, now):
    if row is None or type(row['id']) is not int or not 1 <= row['id'] <= 4294967295:
        raise ValueError('advice unavailable')
    created = row['created_at']
    if type(created) not in (int, float) or not math.isfinite(created) or not 0 <= (now-created)*1000 < MAX_AGE_MS:
        raise ValueError('advice unavailable')
    advice = json.loads(row['output_json'])
    ml = advice.get('suggested_ml') if isinstance(advice, dict) else None
    if type(ml) is not int or not 100 <= ml <= 400:
        raise ValueError('invalid suggested volume')
    # DB provenance, not caller/model-supplied actuation flags, is authoritative.
    model_backed = (type(row['fallback']) in (bool, int) and row['fallback'] == 0 and
                    advice.get('fallback') is False and advice.get('source') == 'model')
    return dict(version=1, **context, advice_id=row['id'], age_ms=int((now-created)*1000),
                suggested_ml=ml, model_backed=model_backed, actuation_allowed=False)
