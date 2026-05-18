"""测试可选角色 LLM 分类。"""

from types import SimpleNamespace

from opc import roles


class FakeAnthropic:
    def __init__(self, text):
        self.messages = SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(content=[SimpleNamespace(text=text)]))


def test_infer_optional_roles_uses_llm_classifier(monkeypatch):
    monkeypatch.setattr(roles.anthropic, "Anthropic", lambda: FakeAnthropic('{"roles": ["ops", "architect", "unknown"]}'))

    result = roles.infer_optional_roles("发布前检查部署风险")

    assert result == {"ops", "architect"}


def test_infer_optional_roles_falls_back_to_keywords(monkeypatch):
    def fail_client():
        raise RuntimeError("offline")

    monkeypatch.setattr(roles.anthropic, "Anthropic", fail_client)

    result = roles.infer_optional_roles("需要做竞品用户研究")

    assert result == {"growth"}


def test_invalid_classifier_payload_falls_back_to_keywords(monkeypatch):
    monkeypatch.setattr(roles.anthropic, "Anthropic", lambda: FakeAnthropic('{"roles": "ops"}'))

    result = roles.infer_optional_roles("需要设计模块边界")

    assert result == {"architect"}
