"""Rendering a pack through Jinja. Templates only — no logic, no composition.

The environment is deliberately spare: `autoescape` off because these are plain
text documents rather than HTML, `StrictUndefined` on because a template that
silently prints nothing for a missing field is how a pack loses its citation
without anyone noticing.

`trim_blocks` and `lstrip_blocks` keep the templates readable without the
document filling with blank lines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .pack import PACK_TEMPLATE, TEMPLATE_ROOT, money, written_date
from .wording import condition as condition_wording
from .wording import label as field_label
from .wording import value as field_value

if TYPE_CHECKING:  # pragma: no cover - import cycle, types only
    from .pack import EvidencePack


def environment() -> Environment:
    """The Jinja environment every pack is rendered through."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_ROOT),
        autoescape=False,  # plain text, not markup
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    # One formatting of a rent across voice, web and PDF. See GLOSSARY section 4.
    env.filters["money"] = money
    env.filters["written_date"] = written_date

    # Vocabulary lives in wording.py, never in a template. A translator editing
    # an Arabic template must not have to also know that `gap_pct` is called
    # "how far below the average", and a template that spells its own labels is
    # a second place for the glossary to drift from.
    env.filters["field_label"] = field_label
    env.filters["condition_wording"] = condition_wording
    env.globals["field_value"] = field_value
    return env


def render_text(pack: EvidencePack) -> str:
    """Render a pack to plain text in its own language."""
    template = environment().get_template(f"{pack.language}/{PACK_TEMPLATE}")
    return template.render(pack=pack, records=pack.records)
