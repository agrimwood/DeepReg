import os

import numpy as np
import tensorflow as tf
from tqdm import tqdm

from deepreg.dataset.util import mkdir_if_not_exists

TF_RECORDS_COMPRESSION_TYPE = "GZIP"


def _bytes_feature(value):
    """Returns a bytes_list from a string / byte."""
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))


def _float_feature(value):
    """Returns a float_list from a float or a list of such type."""
    if isinstance(value, float):
        value = [value]
    return tf.train.Feature(float_list=tf.train.FloatList(value=value))


def _int64_feature(value):
    """Returns an int64_list from a int or a list of such type."""
    if isinstance(value, int):
        value = [value]
    return tf.train.Feature(int64_list=tf.train.Int64List(value=value))


def serializer(example):
    inputs, fixed_label = example
    moving_image, fixed_image, moving_label, indices = inputs
    feature = {
        "moving_image": _bytes_feature(moving_image.astype(np.float32).tobytes()),
        "fixed_image": _bytes_feature(fixed_image.astype(np.float32).tobytes()),
        "moving_label": _bytes_feature(moving_label.astype(np.float32).tobytes()),
        "fixed_label": _bytes_feature(fixed_label.astype(np.float32).tobytes()),
        "indices": _bytes_feature(indices.astype(np.float32).tobytes()),
    }
    example_proto = tf.train.Example(features=tf.train.Features(feature=feature))
    return example_proto.SerializeToString()


def decode_array(data, shape, name=None):
    """

    :param data:
    :param shape: is not tf tensor, otherwise the shape will remain None
    :return:
    """
    return tf.reshape(
        tf.io.decode_raw(data, out_type=tf.float32), shape=shape, name=name
    )


def parser(example_proto, moving_image_shape, fixed_image_shape, num_indices):
    features = {
        "moving_image": tf.io.FixedLenFeature(shape=[], dtype=tf.string),
        "fixed_image": tf.io.FixedLenFeature(shape=[], dtype=tf.string),
        "moving_label": tf.io.FixedLenFeature(shape=[], dtype=tf.string),
        "fixed_label": tf.io.FixedLenFeature(shape=[], dtype=tf.string),
        "indices": tf.io.FixedLenFeature(shape=[], dtype=tf.string),
    }
    example = tf.io.parse_single_example(serialized=example_proto, features=features)

    moving_image = example["moving_image"]
    fixed_image = example["fixed_image"]
    moving_label = example["moving_label"]
    fixed_label = example["fixed_label"]
    indices = example["indices"]

    with tf.name_scope("parser"):
        moving_image = decode_array(
            moving_image, shape=moving_image_shape, name="moving_image"
        )
        moving_label = decode_array(
            moving_label, shape=moving_image_shape, name="moving_label"
        )
        fixed_image = decode_array(
            fixed_image, shape=fixed_image_shape, name="fixed_image"
        )
        fixed_label = decode_array(
            fixed_label, shape=fixed_image_shape, name="fixed_label"
        )
        indices = decode_array(indices, shape=[num_indices], name="indices")

    return (moving_image, fixed_image, moving_label, indices), fixed_label


def write_tfrecords(data_dir, data_generator, examples_per_tfrecord=64):
    """
    :param data_dir: folder path where we save tfrecords
    :param data_generator:
    :param examples_per_tfrecord:
    :return:
    """

    mkdir_if_not_exists(data_dir)
    options = tf.io.TFRecordOptions(compression_type=TF_RECORDS_COMPRESSION_TYPE)

    def write(_examples, _num_tfrecord):
        filename = os.path.join(data_dir, "%d.tfrecords" % _num_tfrecord)
        with tf.io.TFRecordWriter(filename, options=options) as writer:
            for _example in _examples:
                writer.write(serializer(_example))

    num_tf_record = 0
    examples = []
    for example in tqdm(data_generator):
        if len(examples) < examples_per_tfrecord:
            examples.append(example)
        else:
            write(examples, num_tf_record)
            examples = []
            num_tf_record += 1
    if len(examples) > 0:
        write(examples, num_tf_record)


def get_tfrecords_filenames(tfrecord_dir):
    return [
        os.path.join(tfrecord_dir, x)
        for x in os.listdir(tfrecord_dir)
        if x.endswith(".tfrecords")
    ]


def load_tfrecords(filenames, moving_image_shape, fixed_image_shape, num_indices):
    dataset = tf.data.TFRecordDataset(
        filenames, compression_type=TF_RECORDS_COMPRESSION_TYPE
    )
    dataset = dataset.map(
        lambda x: parser(x, moving_image_shape, fixed_image_shape, num_indices),
        num_parallel_calls=tf.data.experimental.AUTOTUNE,
    )
    return dataset
