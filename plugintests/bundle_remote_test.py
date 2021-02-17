import pytest

from owmeta_pytest_plugin import bundle_versions, bundle_fixture_helper

example_bundle = pytest.fixture(bundle_fixture_helper('example/aBundle'))


@bundle_versions('example_bundle', [23])
@pytest.mark.bundle_remote('test.remote')
def test_bundle_remote(owm_project, example_bundle):
    owm_project.fetch(example_bundle)
