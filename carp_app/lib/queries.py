import importlib
try:
    _mod = importlib.import_module("carp_app.queries")
    for _n in dir(_mod):
        if not _n.startswith("_"):
            globals()[_n] = getattr(_mod, _n)
except Exception:
    pass
