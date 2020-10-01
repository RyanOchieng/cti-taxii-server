import json
import json.decoder
import re
from unittest import mock

import pytest
import pytest_subtests  # noqa: F401

import medallion.config as m_cfg

pytestmark = pytest.mark.usefixtures("empty_environ")


def test_load_config_defaults():
    """
    Ensure that `conf_file` and `conf_dir` arguments have expected defaults.

    We do this since we don't want to attempt to create those files for parsing
    in any of our actual functional tests below.
    """
    assert m_cfg.load_config.__defaults__ == (
        m_cfg.DEFAULT_CONFFILE, m_cfg.DEFAULT_CONFDIR,
    )


def test_load_config_default_file_missing(subtests, tmp_path):
    """
    Confirm that nothing bad happens if the default config file is missing.
    """
    with mock.patch(
        "medallion.config.DEFAULT_CONFFILE", str(tmp_path / "medallion.conf"),
    ) as mock_conf_file_default:
        with subtests.test(msg="conf_dir omitted"):
            config = m_cfg.load_config(conf_file=mock_conf_file_default)
            assert config == {}
        with subtests.test(msg="conf_dir is None"):
            config = m_cfg.load_config(
                conf_file=mock_conf_file_default, conf_dir=None,
            )
            assert config == {}


def test_load_config_non_default_file_missing(subtests, tmp_path):
    """
    Confirm an exception is raised if a non-default config file is missing.
    """
    conf_file = tmp_path / "missing.conf"
    exc_patt = re.escape(repr(str(conf_file)))
    with pytest.raises(FileNotFoundError, match=exc_patt):
        m_cfg.load_config(conf_file=conf_file)


def test_load_config_default_dir_missing(subtests, tmp_path):
    """
    Confirm that nothing bad happens if the default config dir is missing.
    """
    with mock.patch(
        "medallion.config.DEFAULT_CONFDIR", str(tmp_path / "medallion.d"),
    ) as mock_conf_dir_default:
        with subtests.test(msg="conf_file omitted"):
            config = m_cfg.load_config(conf_dir=mock_conf_dir_default,)
            assert config == {}
        with subtests.test(msg="conf_file is None"):
            config = m_cfg.load_config(
                conf_dir=mock_conf_dir_default, conf_file=None,
            )
            assert config == {}


def test_load_config_non_default_dir_missing(tmp_path):
    """
    Confirm an exception is raised if a non-default config dir is missing.
    """
    conf_dir = tmp_path / "missing.d"
    exc_patt = re.escape(repr(str(conf_dir)))
    with pytest.raises(FileNotFoundError, match=exc_patt):
        m_cfg.load_config(conf_dir=conf_dir)


@pytest.mark.parametrize(
    "confdata", ({}, {"foo": "bar"}, {"foo": {"bar": ["baz", ]}}, )
)
def test_load_config_json_objects(confdata, subtests, tmp_path):
    """
    Confirm that config files get loaded correctly.
    """
    conf_file = tmp_path / "medallion.conf"
    json.dump(confdata, conf_file.open("w"))
    with subtests.test(msg="Used as config file"):
        assert m_cfg.load_config(conf_file=conf_file) == confdata
    with subtests.test(msg="Used from config dir"):
        assert m_cfg.load_config(conf_dir=tmp_path) == confdata


@pytest.mark.parametrize(
    "confdata", ([], ["foo", "bar"], "", 42, )
)
def test_load_config_file_json_not_objects(confdata, subtests, tmp_path):
    """
    Confirm that config files with non-JSON-object data are rejected.

    Specifically, we cannot allow the top level JSON type be anything other
    than an object since we rely on being able to merge objects from the
    various config files and the environment variable collection logic.
    """
    conf_file = tmp_path / "medallion.conf"
    json.dump(confdata, conf_file.open("w"))
    with subtests.test(msg="Used as config file"):
        with pytest.raises(TypeError, match="must contain a JSON object"):
            m_cfg.load_config(conf_file=conf_file)
    with subtests.test(msg="Used from config dir"):
        with pytest.raises(TypeError, match="must contain a JSON object"):
            m_cfg.load_config(conf_dir=tmp_path)


@pytest.mark.parametrize("confdata", (
    "", "[,]", "{,}",
    "'wrong quotes'", "{missing: quotes}", '{"trailing": "comma",}',
    "\x7FELFverywrong",
))
def test_load_config_file_bad_json(confdata, subtests, tmp_path):
    """
    Confirm that config files with non-JSON-object data are rejected.

    Specifically, we cannot allow the top level JSON type be anything other
    than an object since we rely on being able to merge objects from the
    various config files and the environment variable collection logic.
    """
    conf_file = tmp_path / "medallion.conf"
    conf_file.open("w").write(confdata)
    with subtests.test(msg="Used as config file"):
        with pytest.raises(ValueError, match="Invalid JSON") as exc:
            m_cfg.load_config(conf_file=conf_file)
        assert isinstance(exc.value.__cause__, json.decoder.JSONDecodeError)
    with subtests.test(msg="Used from a config dir"):
        with pytest.raises(ValueError, match="Invalid JSON") as exc:
            m_cfg.load_config(conf_dir=tmp_path)
        assert isinstance(exc.value.__cause__, json.decoder.JSONDecodeError)


def test_env_config_empty_env(subtests):
    """
    Confirm that the `MedallionConfig` return an empty dict from an empty env.

    This test module does this for all tests but an explicit one doesn't hurt!
    """
    env = expected = {}
    with subtests.test(msg="Loading config directly"):
        assert m_cfg.MedallionConfig.from_environ(env).as_dict() == expected
    with subtests.test(msg="Loading config via loader"):
        with mock.patch.dict("os.environ", **env, clear=True):
            config_data = m_cfg.load_config(conf_file=None, conf_dir=None)
        assert config_data == expected


def test_env_config_taxii(subtests):
    """
    Confirm that the `MedallionConfig` can get TAXII config from the env.
    """
    env = {
        "MEDALLION_TAXII_MAX_PAGE_SIZE": "42",
    }
    expected = {
        "taxii": {
            "max_page_size": int(env["MEDALLION_TAXII_MAX_PAGE_SIZE"]),
        },
    }
    with subtests.test(msg="Loading config directly"):
        assert m_cfg.MedallionConfig.from_environ(env).as_dict() == expected
    with subtests.test(msg="Loading config via loader"):
        with mock.patch.dict("os.environ", **env, clear=True):
            config_data = m_cfg.load_config(conf_file=None, conf_dir=None)
        assert config_data == expected


def test_env_config_backend_type(subtests):
    """
    Confirm that the `MedallionConfig` can get a backend type from the env.
    """
    env = {
        "MEDALLION_BACKEND_MODULE_CLASS": "MemoryBackend",
    }
    expected = {
        "backend": {
            "module_class": env["MEDALLION_BACKEND_MODULE_CLASS"],
        },
    }
    with subtests.test(msg="Loading config directly"):
        assert m_cfg.MedallionConfig.from_environ(env).as_dict() == expected
    with subtests.test(msg="Loading config via loader"):
        with mock.patch.dict("os.environ", **env, clear=True):
            config_data = m_cfg.load_config(conf_file=None, conf_dir=None)
        assert config_data == expected


def test_env_config_backend_memory(subtests):
    """
    Confirm that the `MedallionConfig` can get `MemoryBackend` config.
    """
    env = {
        "MEDALLION_BACKEND_MODULE_CLASS": "MemoryBackend",
        "MEDALLION_BACKEND_MEMORY_FILENAME": "/path/to/nowhere",
    }
    expected = {
        "backend": {
            "module_class": env["MEDALLION_BACKEND_MODULE_CLASS"],
            # This has to be flattened by the config loader
            env["MEDALLION_BACKEND_MODULE_CLASS"]: {
                "filename": env["MEDALLION_BACKEND_MEMORY_FILENAME"],
            },
        },
    }
    with subtests.test(msg="Loading config directly"):
        assert m_cfg.MedallionConfig.from_environ(env).as_dict() == expected

    expected_flat = {
        "backend": {
            "module_class": env["MEDALLION_BACKEND_MODULE_CLASS"],
            "filename": env["MEDALLION_BACKEND_MEMORY_FILENAME"],
        },
    }
    with subtests.test(msg="Loading config via loader"):
        with mock.patch.dict("os.environ", **env, clear=True):
            config_data = m_cfg.load_config(conf_file=None, conf_dir=None)
        assert config_data == expected_flat


def test_env_config_backend_mongo(subtests):
    """
    Confirm that the `MedallionConfig` can get `MongoBackend` config.
    """
    env = {
        "MEDALLION_BACKEND_MODULE_CLASS": "MongoBackend",
        "MEDALLION_BACKEND_MONGO_URI": "mongodb://user:resu@localhost:27017/",
    }
    expected = {
        "backend": {
            "module_class": env["MEDALLION_BACKEND_MODULE_CLASS"],
            # This has to be flattened by the config loader
            env["MEDALLION_BACKEND_MODULE_CLASS"]: {
                "uri": env["MEDALLION_BACKEND_MONGO_URI"],
            },
        },
    }
    with subtests.test(msg="Loading config directly"):
        assert m_cfg.MedallionConfig.from_environ(env).as_dict() == expected

    expected_flat = {
        "backend": {
            "module_class": env["MEDALLION_BACKEND_MODULE_CLASS"],
            "uri": env["MEDALLION_BACKEND_MONGO_URI"],
        },
    }
    with subtests.test(msg="Loading config via loader"):
        with mock.patch.dict("os.environ", **env, clear=True):
            config_data = m_cfg.load_config(conf_file=None, conf_dir=None)
        assert config_data == expected_flat
