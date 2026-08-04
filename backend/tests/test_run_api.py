import pytest

from app.scripts.run_api import application_port


def test_application_port_uses_platform_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "10000")

    assert application_port() == 10000


@pytest.mark.parametrize("value", ["not-a-number", "0", "65536"])
def test_application_port_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("PORT", value)

    with pytest.raises(RuntimeError, match="PORT"):
        application_port()
