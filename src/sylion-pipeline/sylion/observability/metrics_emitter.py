import logging
from abc import ABC, abstractmethod

_LOG = logging.getLogger("sylion.metrics")


class MetricEmitter(ABC):
    @abstractmethod
    def counter(self, name, value=1, labels=None): ...

    @abstractmethod
    def histogram(self, name, value, labels=None): ...


class LoggingMetricEmitter(MetricEmitter):
    def __init__(self, logger=None):
        self._logger = logger or _LOG

    def _emit(self, kind, name, value, labels=None):
        emit_w19_metric(name, labels or {}, value, self._logger, kind)

    def counter(self, name, value=1, labels=None):
        self._emit("counter", name, value, labels)

    def histogram(self, name, value, labels=None):
        self._emit("histogram", name, value, labels)


def emit_w19_metric(name: str, labels: dict, value: float, logger=None, kind: str = "gauge") -> None:
    (logger or _LOG).info(
        "metric",
        extra={"metric": {"type": kind, "name": name, "labels": labels, "value": value}},
    )
