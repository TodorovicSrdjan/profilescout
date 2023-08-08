from abc import ABC, abstractmethod


class DetectionStrategy(ABC):
    """Interface/Base class for profile detection strategy"""

    @abstractmethod
    def successful(self):
        pass

    @abstractmethod
    def get_result(self):
        pass
        pass

    @abstractmethod
    def reset(self):
        pass
