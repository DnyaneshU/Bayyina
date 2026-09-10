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


def environment(language: str = "en") -> Environment:
    """The Jinja environment a pack is rendered through.

    Built per language so the vocabulary filters can be bound to it. The
    alternative - passing the language at every call site in every template -
    puts the same argument in forty places and makes forgetting it in one of
    them silently produce a document in two languages.
    """
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
    env.filters["written_date"] = lambda value: written_date(value, language)

    # Vocabulary lives in wording.py, never in a template. A translator editing
    # an Arabic template must not have to also know that `gap_pct` is called
    # "how far below the average", and a template that spells its own labels is
    # a second place for the glossary to drift from.
    env.filters["field_label"] = lambda name: field_label(name, language)
    env.filters["condition_wording"] = lambda name: condition_wording(name, language)
    env.globals["field_value"] = lambda name, raw: field_value(name, raw, language)
    return env


def render_text(pack: EvidencePack) -> str:
    """Render a pack to plain text in its own language."""
    template = environment(pack.language).get_template(f"{pack.language}/{PACK_TEMPLATE}")
    return template.render(pack=pack, records=pack.records)
