from abc import ABC, abstractmethod
from typing import List

from apps.rules.utils.rule_engine_utils import TelemetryEvent


class TelemetryRepository(ABC):
    """
    Abstract repository for retrieving telemetry data within a time window.

    This abstraction decouples the rule engine from the underlying
    storage implementation (e.g., PostgreSQL, Redis).
    """

    @abstractmethod
    def get_in_window(self, telemetry: TelemetryEvent, minutes: int) -> List[TelemetryEvent]:
        """
        Retrieve telemetry records for the same metric and device
        within the specified time window.

        :param telemetry: Incoming telemetry event used as reference.
        :param minutes: Size of the sliding time window in minutes.
        :return: Collection of telemetry records or values.
        """
        raise NotImplementedError



