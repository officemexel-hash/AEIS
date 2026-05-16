from sylion.cognitive.idea_lifecycle_transitions import IDEA_LIFECYCLE_TRANSITIONS, is_valid_transition


class IdeaLifecycleValidator:
    VALID_TRANSITIONS: dict[str, set[str]] = IDEA_LIFECYCLE_TRANSITIONS

    @classmethod
    def validate(cls, from_s: str, to_s: str) -> bool:
        return is_valid_transition(from_s, to_s)
