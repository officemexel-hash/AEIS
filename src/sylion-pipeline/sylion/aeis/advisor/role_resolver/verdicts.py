from dataclasses import dataclass


@dataclass
class RoleVerdictDistribution:
    approve: int = 0
    reject: int = 0
    conditional: int = 0

    def to_dict(self) -> dict[str, int]:
        return vars(self)


def compute_distribution(by_model: list[dict]) -> dict[str, int]:
    dist = RoleVerdictDistribution()
    for item in by_model:
        verdict = item["verdict"]
        if verdict in dist.to_dict():
            setattr(dist, verdict, getattr(dist, verdict) + 1)
    return dist.to_dict()
