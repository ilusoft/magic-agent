"""Tests for the workflow helper functions (Math, Strings, Arrays, Dates)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from src.application.workflows.expressions.helpers import (
    ArrayHelpers,
    DateHelpers,
    StringHelpers,
    WorkflowHelperRegistry,
)


class TestAddToArray:
    """Regression tests for ``addToArray``."""

    def test_appends_to_existing_list(self) -> None:
        assert ArrayHelpers.addToArray([1, 2], 3) == [1, 2, 3]

    def test_appends_to_empty_list(self) -> None:
        assert ArrayHelpers.addToArray([], "item") == ["item"]

    def test_string_first_arg_does_not_iterate_chars(self) -> None:
        """Regression: ``list("Hola mundo")`` iterates the string as
        characters. The helper must wrap a non-list in ``[...]`` so the
        string survives as a single element.
        """
        result = ArrayHelpers.addToArray("Hola mundo", "world")
        assert result == ["Hola mundo", "world"]

    def test_non_list_first_arg_is_wrapped(self) -> None:
        """Any non-list first argument should be wrapped, not iterated."""
        result = ArrayHelpers.addToArray(42, "x")
        assert result == [42, "x"]

        result = ArrayHelpers.addToArray({"k": 1}, "x")
        assert result == [{"k": 1}, "x"]

    def test_returns_new_list_does_not_mutate_input(self) -> None:
        original = [1, 2]
        result = ArrayHelpers.addToArray(original, 3)
        assert result == [1, 2, 3]
        assert original == [1, 2]


class TestNowHelpers:
    """``now()`` / ``nowUtc()`` / ``nowLocal()`` / ``today()``.

    The whole point of these helpers is to ground a workflow in the
    *actual* run time, so a prompt like "today is {{ now() }}" stops
    drifting further from reality on every invocation. The tests
    focus on three properties:

    1. The output is a non-empty string the LLM can read.
    2. The value tracks the host's wall clock (not a baked-in
       constant from the agent JSON).
    3. The defaults match the documented contract: ``now`` /
       ``nowUtc`` are UTC ISO 8601; ``nowLocal`` is local ISO 8601
       with the host's offset; ``today`` is ``YYYY-MM-DD``.
    """

    def test_now_returns_parseable_utc_iso_string(self) -> None:
        result = DateHelpers.now()

        # ``datetime.fromisoformat`` accepts the offset form
        # produced by ``datetime.isoformat`` (e.g. ``+00:00``).
        # Round-tripping catches accidental format regressions
        # (e.g. dropping the timezone offset).
        parsed = datetime.fromisoformat(result)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)

    def test_now_utc_matches_now(self) -> None:
        # ``now`` and ``nowUtc`` are documented aliases, so the
        # parser should accept both and produce a string in the
        # same shape. They need not be byte-identical (call
        # ordering can produce a 1-microsecond difference), but
        # both must round-trip to the same UTC instant.
        now = datetime.fromisoformat(DateHelpers.now())
        now_utc = datetime.fromisoformat(DateHelpers.nowUtc())
        # ``utcoffset()`` on two different calls must be equal
        # (both UTC) and the wall-clock values must be within
        # the millisecond — generous, but it rules out the
        # classic "frozen constant" regression.
        assert now.utcoffset() == now_utc.utcoffset()
        assert abs((now - now_utc).total_seconds()) < 1

    def test_now_with_format_uses_strftime(self) -> None:
        result = DateHelpers.now("%Y-%m-%d")
        # Strict match: ``strftime("%Y-%m-%d")`` is 10 chars and
        # all digits + hyphens. Anything else means the format
        # argument was silently ignored.
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", result), result

    def test_now_local_includes_local_offset(self) -> None:
        result = DateHelpers.nowLocal()
        parsed = datetime.fromisoformat(result)
        # Must NOT be the same offset as ``now()`` (UTC) on any
        # host whose local timezone isn't UTC, which is the
        # whole point of having a separate helper.
        utc_result = DateHelpers.now()
        utc_parsed = datetime.fromisoformat(utc_result)
        # If the host happens to be UTC, the two values will be
        # identical — that's fine, skip the rest of the check.
        if parsed.utcoffset() == utc_parsed.utcoffset():
            pytest.skip("host timezone is UTC; cannot distinguish nowLocal from now")

        # And the offset must reflect the host's *local* zone
        # (with DST) — i.e. it has to match
        # ``datetime.now().astimezone().utcoffset()``.
        expected_offset = datetime.now(timezone.utc).astimezone().utcoffset()
        assert parsed.utcoffset() == expected_offset

    def test_now_local_with_format_uses_strftime(self) -> None:
        result = DateHelpers.nowLocal("%Y/%m/%d %H:%M")
        assert re.fullmatch(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}", result), result

    def test_today_returns_local_date_in_iso_shape(self) -> None:
        result = DateHelpers.today()

        # ``today()`` is documented as ``YYYY-MM-DD`` in the
        # *local* timezone. A naive ``strftime("%Y-%m-%d")`` on
        # ``astimezone()`` gives that, so the regex is the
        # primary contract test.
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", result), result

        # And the value must agree with ``nowLocal("%Y-%m-%d")``
        # — not, say, a stale UTC date that was baked in at
        # package-install time.
        now_local_date = DateHelpers.nowLocal("%Y-%m-%d")
        assert result == now_local_date

    def test_helpers_are_discoverable_via_registry(self) -> None:
        """The frontend helper picker (``/api/workflows/helpers``)
        reads from ``WorkflowHelperRegistry``. The new helpers
        must show up there, with the right category, so the UI
        can render them in the same dates group as the other
        date helpers.

        Note: the registry currently exposes descriptors under
        their lowercased name (the same key the case-insensitive
        ``invoke`` uses). The lookup is case-insensitive here so
        the test stays correct even if a future change restores
        the original case in the descriptor.
        """
        registry = WorkflowHelperRegistry()
        descriptors = {d.name.lower(): d for d in registry.get_helpers()}

        for name in ("now", "nowutc", "nowlocal", "today"):
            assert name in descriptors, f"helper {name!r} missing from registry"
            assert descriptors[name].category == "Dates", (
                f"helper {name!r} should be in the Dates category, "
                f"got {descriptors[name].category!r}"
            )

    def test_registry_invokes_helpers_with_no_args(self) -> None:
        """The registry's ``invoke`` must accept zero-arg calls
        for ``now``/``nowUtc``/``nowLocal``/``today`` and not
        raise the "missing required argument" path the legacy
        helper registry used to take.
        """
        registry = WorkflowHelperRegistry()
        # None of these should raise.
        for name in ("now", "nowUtc", "nowLocal", "today"):
            result = registry.invoke(name, [])
            assert isinstance(result, str)
            assert result  # non-empty


class TestHelperDescriptorShape:
    """The ``/api/workflows/helpers`` payload is the contract the
    expression-builder dialog consumes. These tests guard that
    contract so the dialog can group helpers by return type and
    render parameter types alongside parameter names.
    """

    @pytest.fixture
    def registry(self) -> WorkflowHelperRegistry:
        return WorkflowHelperRegistry()

    @pytest.fixture
    def descriptors_by_name(self, registry) -> dict[str, dict]:
        # ``get_helpers`` lowercases the registered name in the
        # descriptor (a pre-existing behaviour, see
        # ``test_helpers_are_discoverable_via_registry``), so we
        # index by the lowercased name for stable lookups. The
        # values are plain dicts (``model_dump()``) so the tests
        # can subscript with ``["returnType"]`` etc. without
        # the Pydantic attribute-vs-item gotcha.
        return {
            d.name.lower(): d.model_dump()
            for d in registry.get_helpers()
        }

    def test_descriptors_carry_return_type(self, descriptors_by_name: dict) -> None:
        """Each descriptor must include a ``returnType`` so the
        dialog can group by return kind. The new ``now`` family
        returns strings; ``dateAdd`` returns datetimes; the
        length helper returns numbers. Without this field the
        dialog falls back to a single "Returns value" bucket
        and the new helpers become hard to find.
        """
        assert descriptors_by_name["now"]["returnType"] == "string"
        assert descriptors_by_name["nowutc"]["returnType"] == "string"
        assert descriptors_by_name["nowlocal"]["returnType"] == "string"
        assert descriptors_by_name["today"]["returnType"] == "string"
        # Sanity: a non-string helper still reports a real kind.
        assert descriptors_by_name["arraylength"]["returnType"] == "number"
        assert descriptors_by_name["dateadd"]["returnType"] == "datetime"

    def test_descriptors_carry_parameter_type(self, descriptors_by_name: dict) -> None:
        """Each parameter must carry a ``type`` matching the
        helper's signature, so the dialog can render e.g.
        ``format (string)`` next to the parameter.

        Specifically guards the PEP 604 ``str | None`` annotation
        on the new helpers — older resolver code returned
        ``"value"`` for any Union whose ``__origin__`` was
        ``None`` (which is the case for ``X | Y`` on 3.10+).
        """
        for name in ("now", "nowutc", "nowlocal"):
            descriptor = descriptors_by_name[name]
            assert len(descriptor["parameters"]) == 1
            param = descriptor["parameters"][0]
            assert param["name"] == "format"
            assert param["type"] == "string", (
                f"{name}'s format param resolved to {param['type']!r}; "
                "expected 'string' (regression of the PEP 604 Union bug)."
            )
            assert param["optional"] is True

        assert descriptors_by_name["today"]["parameters"] == []

    def test_parameters_appear_in_signature_order(self, descriptors_by_name: dict) -> None:
        """``@workflow_helper_param`` decorators apply bottom-up,
        which inverts the signature order. The dialog (and any
        downstream tooling) expects the parameters in the same
        order the developer wrote them in the function
        signature, not the decorator stack order.
        """
        # ``dateAdd(date, amount, unit)`` is declared that way
        # in the source. The legacy behaviour reported them as
        # ``[unit, amount, date]`` (reversed). The fix re-orders
        # the descriptor to match the signature.
        date_add = descriptors_by_name["dateadd"]
        names = [p["name"] for p in date_add["parameters"]]
        assert names == ["date", "amount", "unit"], (
            f"dateAdd parameters out of order: {names}"
        )

        # The first parameter (date) takes an ISO string, so
        # the type resolver falls back to ``"value"`` (Union
        # of two non-None types is intentionally ambiguous).
        # The next one (amount) is a number, and unit is a
        # string. The ordering fix must not regress the type
        # resolution.
        types = [p["type"] for p in date_add["parameters"]]
        assert types[1] == "number"
        assert types[2] == "string"

    def test_descriptors_match_dotnet_schema(self, descriptors_by_name: dict) -> None:
        """Spot-check that every parameter carries the fields
        the .NET side also publishes, so the dialog renders
        both backends consistently.
        """
        expected_param_keys = {"name", "type", "description", "optional", "default"}
        for descriptor in descriptors_by_name.values():
            for param in descriptor["parameters"]:
                missing = expected_param_keys - set(param.keys())
                assert not missing, (
                    f"helper {descriptor['name']!r} param {param['name']!r} "
                    f"is missing keys: {missing}"
                )

        expected_descriptor_keys = {
            "name",
            "description",
            "category",
            "returnType",
            "parameters",
            "examples",
        }
        for descriptor in descriptors_by_name.values():
            missing = expected_descriptor_keys - set(descriptor.keys())
            assert not missing, (
                f"helper {descriptor['name']!r} is missing keys: {missing}"
            )
