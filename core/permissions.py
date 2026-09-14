"""Role matrix: basico views, premium exports, admin manages."""
from __future__ import annotations

VIEWER = {"basico", "premium", "admin"}
EXPORTER = {"premium", "admin"}
ADMIN = {"admin"}

CAN: dict[str, set[str]] = {
    "view": set(VIEWER),
    "search": set(VIEWER),
    "export": set(EXPORTER),
    "print": set(EXPORTER),
    "share": set(EXPORTER),
    "generate_newsletter": set(EXPORTER),
    "add_news": set(ADMIN),
    "edit_weights": set(ADMIN),
    "manage_accounts": set(ADMIN),
    "configure_ai": set(ADMIN),
    "run_pipeline": set(ADMIN),
}

CAPABILITIES: tuple[str, ...] = tuple(CAN)


def can(role: str, capability: str) -> bool:
    return role in CAN.get(capability, set())
