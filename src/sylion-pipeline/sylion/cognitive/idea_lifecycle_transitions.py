IDEA_LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted", "archived", "soft_deleted"},
    "submitted": {"draft", "under_review", "rejected", "soft_deleted"},
    "under_review": {"submitted", "approved", "blocked", "rejected", "soft_deleted"},
    "approved": {"in_progress", "blocked", "archived", "soft_deleted"},
    "in_progress": {"blocked", "completed", "archived", "soft_deleted"},
    "blocked": {"in_progress", "rejected", "archived", "soft_deleted"},
    "completed": {"archived", "soft_deleted"},
    "rejected": {"draft", "archived", "soft_deleted"},
    "archived": {"draft", "soft_deleted"},
    "soft_deleted": {"archived", "hard_deleted"},
    "hard_deleted": set(),
}


def is_valid_transition(from_s: str, to_s: str) -> bool:
    return to_s in IDEA_LIFECYCLE_TRANSITIONS.get(from_s, set())


class IdeaLifecycleTransitions:
    VALID_TRANSITIONS = IDEA_LIFECYCLE_TRANSITIONS

    @classmethod
    def is_valid_transition(cls, from_s: str, to_s: str) -> bool:
        return is_valid_transition(from_s, to_s)
