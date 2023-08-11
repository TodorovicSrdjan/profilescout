import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model

from profilescout.common.constants import ConstantsNamespace
from profilescout.common.interfaces import ImageProfileClassifier

constants = ConstantsNamespace

CLASSIFIERS_DIR = os.path.abspath(
    os.path.join(__file__, os.pardir, 'classifiers'))


class ScoobyDemoClassifier(ImageProfileClassifier):
    def __init__(self, path):
        self.__model = None
        self.__path = path
        self.__load_model(path)

    def __load_model(self, path):
        if self.__model is None:
            self.__model = load_model(path)
        return self.__model

    def preprocess(self, image, resize_width=360, resize_height=480):
        image = tf.image.rgb_to_grayscale(image)
        resized = tf.image.resize(image, [resize_height, resize_width])
        reshaped = tf.reshape(resized, (1, resize_height, resize_width, 1))
        normalized = tf.divide(reshaped, 255.0)
        return normalized

    def predict(self, image, width, height, channels=3, verbose=0):
        array = np.array(image)

        # Ensure the array has 3 channels
        array = array.reshape((1,) + array.shape)

        tensor = tf.convert_to_tensor(array, dtype=tf.uint8)
        preprocessed_image = self.preprocess(tensor)
        is_profile_percetage = self.__model(preprocessed_image, training=False)

        if is_profile_percetage.shape == (1, 2):
            is_profile_percetage = is_profile_percetage[0][1]

        if is_profile_percetage > constants.PREDICTION_THRESHOLD:
            return True

        return False
