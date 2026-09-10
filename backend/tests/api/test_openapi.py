"""The published API documentation, checked rather than hoped for.

The OpenAPI document is how anyone integrating with Bayyina learns what it does
— and it is generated, so it degrades silently. An endpoint added without a
docstring produces a page with a path, a schema and nothing explaining when a
person would call it.
"""

import pytest

from bayyina.api.app import create_app
from bayyina.settings import Settings


@pytest.fixture(scope="module")
def spec(tmp_path_factory) -> dict:
    app = create_app(
        audit_path=tmp_path_factory.mktemp("audit") / "audit.jsonl",
        market_db=tmp_path_factory.mktemp("market") / "absent.duckdb",
        case_db=tmp_path_factory.mktemp("store") / "cases.db",
        settings=Settings(),
    )
    return app.openapi()


def _operations(spec: dict):
    for path, methods in sorted(spec["paths"].items()):
        for method, operation in methods.items():
            yield f"{method.upper()} {path}", operation


def _resolve(spec: dict, schema: dict) -> dict:
    """Follow a `$ref` into components.

    FastAPI puts a model's `json_schema_extra` on the component schema and makes
    the request body a reference to it, which is where Swagger UI reads examples
    from. A test that looked only at the content block would report every body
    as undocumented while the docs page showed the examples perfectly.
    """
    ref = schema.get("$ref")
    if not ref:
        return schema
    name = ref.rsplit("/", 1)[-1]
    return spec["components"]["schemas"].get(name, {})


def _examples(spec: dict, operation: dict) -> list:
    body = operation.get("requestBody")
    if not body:
        return []
    content = body.get("content", {}).get("application/json", {})
    found = content.get("examples") or content.get("example")
    if found:
        return found if isinstance(found, list) else [found]
    resolved = _resolve(spec, content.get("schema", {}))
    found = resolved.get("examples") or resolved.get("example")
    if not found:
        return []
    return found if isinstance(found, list) else [found]


def test_the_api_describes_itself(spec):
    assert spec["info"]["title"]
    assert spec["info"].get("description", "").strip(), (
        "the API has no description, so /docs opens on a bare list of paths"
    )


def test_every_endpoint_has_a_summary(spec):
    """The one line shown beside the path in the endpoint list."""
    missing = [name for name, op in _operations(spec) if not op.get("summary", "").strip()]
    assert not missing, f"these endpoints have no summary: {missing}"


def test_every_endpoint_explains_when_to_call_it(spec):
    """A schema says what the shape is. Only prose says what it is for."""
    thin = [name for name, op in _operations(spec) if len(op.get("description", "").strip()) < 40]
    assert not thin, f"these endpoints have no useful description: {thin}"


def test_every_request_body_carries_an_example(spec):
    """A reader should be able to copy something that works.

    An endpoint documented only by its schema makes the reader assemble a first
    request out of field names, and the two POST bodies here have nested
    provenance fields nobody guesses correctly.
    """
    missing = [
        name
        for name, operation in _operations(spec)
        if operation.get("requestBody") and not _examples(spec, operation)
    ]
    assert not missing, f"these request bodies have no example: {missing}"


def test_the_evaluate_examples_cover_both_ways_to_get_a_market_figure(spec):
    """The distinction the endpoint exists to keep straight.

    Supplying both a figure and a dwelling is refused, so the docs must show
    each on its own rather than one combined body a reader would copy.
    """
    rendered = str(_examples(spec, spec["paths"]["/evaluate"]["post"]))

    assert "dwelling" in rendered, "no example derives the market figure"
    assert "user_supplied" in rendered, "no example supplies the market figure"


def test_no_example_supplies_both_a_figure_and_a_dwelling(spec):
    """A copyable example the endpoint would reject with a 422."""
    for example in _examples(spec, spec["paths"]["/evaluate"]["post"]):
        value = example.get("value", example)
        assert not (value.get("dwelling") and "market_average_rent" in value.get("inputs", {})), (
            "an example supplies both a dwelling and a market figure, which the endpoint refuses"
        )


def test_the_documented_examples_are_actually_accepted(tmp_path_factory, spec):
    """The guard that matters.

    An example that no longer validates is worse than none: a reader copies it,
    gets a 422, and concludes the API is broken. This runs each documented body
    against the real endpoint.
    """
    from fastapi.testclient import TestClient

    client = TestClient(
        create_app(
            audit_path=tmp_path_factory.mktemp("audit2") / "audit.jsonl",
            market_db=tmp_path_factory.mktemp("market2") / "absent.duckdb",
            case_db=tmp_path_factory.mktemp("store2") / "cases.db",
            settings=Settings(public_rate_limit_per_minute=10_000),
        )
    )

    for path, method, expected in (
        ("/evidence-pack", "post", {200}),
        # The dwelling example needs market data this fixture does not have, so
        # 503 is the correct answer to it here — what must not happen is a 422,
        # which would mean the documented body does not validate.
        ("/evaluate", "post", {200, 503}),
    ):
        examples = _examples(spec, spec["paths"][path][method])
        assert examples, f"no documented example for {method.upper()} {path}"
        for example in examples:
            value = example.get("value", example)
            response = client.request(method.upper(), path, json=value)
            assert response.status_code in expected, (
                f"the documented example for {method.upper()} {path} returned "
                f"{response.status_code}: {response.text[:200]}"
            )


def test_every_documented_input_is_one_the_rule_declares(spec, signed_rules):
    """The check that does not depend on market data.

    `test_the_documented_examples_are_actually_accepted` cannot catch a renamed
    input on the dwelling example: that request 503s on the absent comparables
    database *before* the evaluator looks at the inputs at all, so a corrupted
    field name sails through. Proven by breaking it — the test stayed green.

    This reads the example against the signed rule it names, which needs no
    database and no network, and fails on exactly the mistake the other test
    misses.
    """
    offenders: list[str] = []

    for path in ("/evaluate", "/evidence-pack"):
        for example in _examples(spec, spec["paths"][path]["post"]):
            value = example.get("value", example)
            rule = signed_rules[value["rule_id"]]
            declared = set(rule.inputs)

            for name in value.get("inputs", {}):
                if name not in declared:
                    offenders.append(f"{path}: inputs.{name} is not declared by {rule.id}")
            for name in value.get("input_sources", {}):
                if name not in declared:
                    offenders.append(f"{path}: input_sources.{name} is not declared by {rule.id}")

            # Everything the rule requires and does not derive must be present,
            # or the example is one a reader copies and gets a 422 from.
            for name, spec_for in rule.inputs.items():
                if spec_for.required and not spec_for.derived:
                    assert name in value.get("inputs", {}), (
                        f"{path}: the example omits the required input {name!r}"
                    )

    assert not offenders, "documented examples name inputs no rule has:\n  " + "\n  ".join(
        offenders
    )
