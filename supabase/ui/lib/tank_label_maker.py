# shim to keep old pages working while using the new 2x1.5in renderer
from . import labels_roll_2x1_5 as _impl

def render_tank_labels_pdf(df, **kwargs):
    for name in ("render_tank_labels_pdf", "render_labels_pdf", "render"):
        f = getattr(_impl, name, None)
        if callable(f):
            return f(df, **kwargs)
    raise RuntimeError("labels_roll_2x1_5 has no render_{tank_}labels_pdf function")

