import os

from profilescout.common.constants import ConstantsNamespace

import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model


constants = ConstantsNamespace

CLASSIFIERS_DIR = os.path.abspath(
    os.path.join(__file__,
                 os.pardir,
                 os.pardir,
                 os.pardir,
                 'classifiers'))


class ImageClassifier:

    __model = None

    def __init__(self, classifier_name):
        self.__classifier_name = classifier_name

        path = os.path.join(CLASSIFIERS_DIR,  f'{classifier_name}.h5')
        self.__classifier_path = path

    def __load_model(self):
        if self.__model is None:
            self.__model = load_model(self.__classifier_path)
        return self.__model

    def __preprocess_scooby(self, image, resize_height=480, resize_width=360):
        image = tf.image.rgb_to_grayscale(image)
        resized = tf.image.resize(image, [resize_height, resize_width])
        reshaped = tf.reshape(resized, (1, resize_height, resize_width, 1))
        normalized = tf.divide(reshaped, 255.0)

        return normalized

    def __preprocess_batman(self, image, resize_height=360, resize_width=480):
        image = tf.image.rgb_to_grayscale(image)
        resized = tf.image.resize(image, [resize_height, resize_width])
        reshaped = tf.reshape(resized, (1, resize_height, resize_width, 1))
        normalized = tf.divide(reshaped, 255.0)

        return normalized

    def predict(self, image, height, width, channels=3, verbose=0):
        self.__load_model()

        array = np.array(image)

        # Ensure the array has 3 channels
        array = array.reshape((1,) + array.shape)

        tensor = tf.convert_to_tensor(array, dtype=tf.uint8)

        # TODO refactor
        preprocessed_image = tensor
        if 'scooby' in self.__classifier_name:
            preprocessed_image = self.__preprocess_scooby(tensor)
        elif 'batman' in self.__classifier_name:
            preprocessed_image = self.__preprocess_batman(tensor)

        is_profile_percetage = self.__model(preprocessed_image, training=False)
        if is_profile_percetage > constants.PREDICTION_THRESHOLD:
            return True

        return False
