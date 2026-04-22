import time

_request_log = {}


def is_rate_limited(key, limit=12, window_seconds=10):
    now = time.time()

    if key not in _request_log:
        _request_log[key] = []

    _request_log[key] = [t for t in _request_log[key] if now - t < window_seconds]

    if len(_request_log[key]) >= limit:
        return True

    _request_log[key].append(now)
    return False