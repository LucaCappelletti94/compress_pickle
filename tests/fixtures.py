import codecs
import io
import itertools
import os
import pathlib
import random
import string
import sys

import pytest

import compress_pickle
from compress_pickle.compressers import get_compression_write_mode
from compress_pickle.utils import (
    _infer_compression_from_path,
    _set_default_extension,
    _stringyfy_path,
)

COMPRESSION_NAMES = [None, "pickle", "gzip", "bz2", "lzma", "zipfile", "lz4"]
UNHANDLED_COMPRESSIONS = ["gzip2", "tar", "zip", 3, [1, 3]]
PICKLER_NAMES = ["pickle", "optimized_pickle", "marshal", "dill", "cloudpickle", "json"]
UNHANDLED_PICKLERS = [None, "tar", "zip", 3, [1, 3]]
VALID_EXTENSIONS = [
    ("pkl", None),
    ("pickle", None),
    ("gz", "gzip"),
    ("bz", "bz2"),
    ("bz2", "bz2"),
    ("lzma", "lzma"),
    ("xz", "lzma"),
    ("zip", "zipfile"),
    ("lz4", "lz4"),
]
INVALID_EXTENSIONS = ["", "unknown"]
FILENAMES = [
    klass(".".join([prefix, extension]) if extension else prefix)
    for prefix, extension, klass in itertools.product(
        ["test_blabla_{}"],
        [e[0] for e in VALID_EXTENSIONS] + INVALID_EXTENSIONS,
        [str, lambda x: bytes(x, "utf-8"), pathlib.Path],
    )
]
UNHANDLED_EXTENSIONS = ["ignore", "warn", "raise"]
FILE_COMPRESSIONS = COMPRESSION_NAMES + ["infer"]
FILE_TYPES = ["file", io.BytesIO, io.BufferedWriter, io.BufferedReader]


@pytest.fixture(scope="function")
def random_message():
    message = (
        "I am the hidden message and I will be dumped with pickle or json "
        + "and compressed with standard libraries. I am very long just to "
        + "ensure that my compressed form takes up less bytes than my "
        + "uncompressed representation. I will end with 12 random chars to "
        + "randomize the message between function calls. I will also include "
        + "a big redundancy string to ensure a smaller compressed size: "
        + "a" * 50
        + "".join(random.choices(string.printable, k=12))
    )
    return message


@pytest.fixture(scope="module", params=COMPRESSION_NAMES, ids=str)
def compressions(request):
    return request.param


@pytest.fixture(scope="module", params=UNHANDLED_COMPRESSIONS, ids=str)
def wrong_compressions(request):
    return request.param


@pytest.fixture(scope="module", params=VALID_EXTENSIONS, ids=str)
def valid_extensions(request):
    return request.param


@pytest.fixture(scope="module", params=INVALID_EXTENSIONS, ids=str)
def invalid_extensions(request):
    return request.param


@pytest.fixture(scope="module", params=FILENAMES, ids=str)
def file(request):
    return request.param


@pytest.fixture(scope="module", params=UNHANDLED_EXTENSIONS, ids=str)
def unhandled_extensions(request):
    return request.param


@pytest.fixture(scope="module", params=[True, False], ids=str)
def set_default_extension(request):
    return request.param


@pytest.fixture(scope="module", params=FILE_COMPRESSIONS, ids=str)
def file_compressions(request):
    return request.param


@pytest.fixture(scope="module", params=FILE_TYPES, ids=str)
def file_types(request):
    return request.param


@pytest.fixture(scope="module", params=PICKLER_NAMES, ids=str)
def pickler_method(request):
    return request.param


@pytest.fixture(
    scope="module",
    params=itertools.product(FILE_COMPRESSIONS + UNHANDLED_COMPRESSIONS, [True, False]),
    ids=str,
)
def compressions_to_validate(request):
    compression, infer_is_valid = request.param
    expected_fail = False
    if compression in UNHANDLED_COMPRESSIONS:
        expected_fail = True
    elif not infer_is_valid and compression == "infer":
        expected_fail = True
    return compression, infer_is_valid, expected_fail


@pytest.fixture(
    scope="module",
    params=zip(
        itertools.product(PICKLER_NAMES, [True]),
        itertools.product(UNHANDLED_PICKLERS, [False]),
    ),
    ids=str,
)
def picklers_to_validate(request):
    return request.param


@pytest.fixture(scope="function")
def preprocess_path_on_path_types(file, compressions, set_default_extension):
    _file = _stringyfy_path(file).format(compressions)
    if isinstance(file, bytes):
        file = codecs.encode(_file, "utf-8")
    elif isinstance(file, pathlib.PurePath):
        file = pathlib.Path(_file)
    else:
        file = _file
    expected_path = _stringyfy_path(file).format(compressions)
    if set_default_extension:
        expected_path = _set_default_extension(expected_path, compression=compressions)
    mode = get_compression_write_mode(compressions)
    yield file, compressions, set_default_extension, mode, expected_path
    os.remove(expected_path)


@pytest.fixture(scope="function")
def preprocess_path_on_file_types(file_types):
    if file_types == "file":
        path = open("test_blabla_stream", "wb")
    else:
        if file_types in (io.BufferedWriter, io.BufferedReader):
            path = file_types(io.BytesIO())
        else:
            path = file_types()
    mode = "write"
    if file_types == io.BufferedReader:
        mode = "read"
    yield path, mode
    if file_types == "file":
        os.remove("test_blabla_stream")


@pytest.fixture(scope="function")
def preprocess_path_on_file_types_and_compressions(
    preprocess_path_on_file_types, compressions
):
    path, mode = preprocess_path_on_file_types
    expected_fail = False
    if mode == "read" and compressions == "zipfile":
        expected_fail = True
    return path, compressions, mode, expected_fail


@pytest.fixture(scope="function")
def dump_load(file, random_message, file_compressions, set_default_extension):
    message = random_message
    _file = _stringyfy_path(file).format(file_compressions)
    if isinstance(file, bytes):
        file = codecs.encode(_file, "utf-8")
    elif isinstance(file, pathlib.PurePath):
        file = pathlib.Path(_file)
    else:
        file = _file
    expected_fail = None
    if file_compressions == "infer":
        try:
            inf_compress = _infer_compression_from_path(file)
        except:
            inf_compress = None
            expected_fail = ValueError
    else:
        inf_compress = file_compressions
    if expected_fail is None:
        if set_default_extension:
            expected_file = _set_default_extension(file, inf_compress)
        else:
            expected_file = _stringyfy_path(file)
    else:
        expected_file = None
    yield (
        message,
        file,
        file_compressions,
        inf_compress,
        set_default_extension,
        expected_file,
        expected_fail,
    )
    if expected_file is not None:
        print(file, file_compressions, set_default_extension, expected_file)
        os.remove(expected_file)


@pytest.fixture(scope="function")
def simple_dump_and_remove(random_message, compressions, pickler_method):
    path = "test_dump_vs_dumps_{}".format(compressions)
    yield (path, compressions, pickler_method, random_message)
    os.remove(path)


@pytest.fixture(scope="function")
def hijack_lz4():
    old_state = compress_pickle.compressers.lz4._lz4_available
    compress_pickle.compressers.lz4._lz4_available = False
    yield
    compress_pickle.compressers.lz4._lz4_available = old_state


@pytest.fixture(scope="function")
def hijack_dill():
    old = compress_pickle.picklers.dill._dill_available
    compress_pickle.picklers.dill._dill_available = False
    yield
    compress_pickle.picklers.dill._dill_available = old


@pytest.fixture(scope="function")
def hijack_cloudpickle():
    old = compress_pickle.picklers.cloudpickle._cloudpickle_available
    compress_pickle.picklers.cloudpickle._cloudpickle_available = False
    yield
    compress_pickle.picklers.cloudpickle._cloudpickle_available = old
