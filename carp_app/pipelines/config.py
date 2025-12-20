from __future__ import annotations

import pathlib
from typing import Any, Dict

import yaml


class PipelineConfigError(RuntimeError):
    pass


def _expand(value: Any, ctx: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        out = value
        for k, v in ctx.items():
            out = out.replace(f"${{{k}}}", str(v))
        return out
    if isinstance(value, dict):
        return {k: _expand(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v, ctx) for v in value]
    return value


def load_pipeline_config(path: str | pathlib.Path) -> Dict[str, Any]:
    path = pathlib.Path(path)
    if not path.exists():
        raise PipelineConfigError(f"config not found: {path}")

    with path.open() as fh:
        cfg = yaml.safe_load(fh)

    if not isinstance(cfg, dict):
        raise PipelineConfigError("config must be a YAML mapping")

    paths = cfg.get("paths", {})
    if not isinstance(paths, dict):
        raise PipelineConfigError("config.paths must be a mapping")

    ctx = {f"paths.{k}": v for k, v in paths.items()}
    cfg = _expand(cfg, ctx)

    if "paths" not in cfg or "raw_dir" not in cfg["paths"]:
        raise PipelineConfigError("config.paths.raw_dir is required")

    raw_dir = pathlib.Path(cfg["paths"]["raw_dir"])
    if not raw_dir.exists():
        raise PipelineConfigError(f"raw_dir does not exist: {raw_dir}")

    return cfg
