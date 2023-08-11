from abc import ABC, abstractmethod


class DetectionStrategy(ABC):
    """Interface/Base class for profile detection strategy"""

    @abstractmethod
    def successful(self):
        pass

    @abstractmethod
    def get_result(self):
        pass

    @abstractmethod
    def reset(self):
        pass


class ProfileClassifier(ABC):
    """Interface/Base class for profile page classifier"""

    @abstractmethod
    def predict(self, data, **kwargs):
        pass

    @abstractmethod
    def preprocess(self, data, **kwargs):
        pass


class ImageProfileClassifier(ProfileClassifier):
    """Interface/Base class for profile page image classifier"""

    @abstractmethod
    def predict(self, image, width, height, channels, verbose, **kwargs):
        pass

    @abstractmethod
    def preprocess(self, image, resize_width=None, resize_heigh=None, **kwargs):
        pass


class TextProfileClassifier(ProfileClassifier):
    """Interface/Base class for profile page text classifier"""

    @abstractmethod
    def predict(self, text, verbose, **kwargs):
        pass

    @abstractmethod
    def preprocess(self, text, **kwargs):
        pass
