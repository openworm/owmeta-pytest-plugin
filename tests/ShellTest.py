from io import StringIO
import shutil
from pathlib import Path
import os

import pytest
from owmeta_core.bundle import Remote
from owmeta_core.bundle.common import BUNDLE_MANIFEST_FILE_NAME
from owmeta_core.bundle.loaders.local import FileURLConfig

from owmeta_pytest_plugin import bundles, bundle_versions, bundle_fixture_helper


# Save the CWD since pytester changes it
CWD = os.getcwd()


def test_sh_multiple_commands(shell_helper):
    assert len(shell_helper.sh('python', 'python')) == 2


def test_sh_with_customizations(shell_helper_with_customizations):
    with shell_helper_with_customizations(customizations='''
    import os
    os.environ['HEY_LOOK_AT_ME'] = "I'm Mr. Meeseeks"
    ''') as shell_helper:
        shell_helper.apply_customizations()
        cmd = r'python -c "import os ; print(os.environ[\"HEY_LOOK_AT_ME\"])"'
        assert shell_helper.sh(cmd).strip() == "I'm Mr. Meeseeks"


def test_owm_project_owmdir(owm_project):
    owm = owm_project.owm()
    assert owm.owmdir.startswith(owm_project.testdir)


@bundles([('example/aBundle', 23)])
def test_owm_project_fetch_bundle(owm_project, bundle):
    bundle_dir = owm_project.fetch(bundle)
    assert bundle_dir.startswith(owm_project.testdir)


example_bundle = pytest.fixture(bundle_fixture_helper('example/aBundle'))


@bundle_versions('example_bundle', [23])
def test_bundle_versions(example_bundle):
    assert example_bundle.remote is not None


def test_remote_bundle(pytester):
    # Set up a remote
    remote = Remote('test', (FileURLConfig(f'file://{pytester.path}/remote-bundles'),))
    sio = StringIO()
    remote.write(sio)
    pytester.makefile('.remote', test=sio.getvalue())

    # Set up the test that will be run
    pytester.copy_example('bundle_remote_test.py')

    # Copy the bundle(s) we use in the test
    shutil.copytree(Path(CWD, 'bundles'), Path(pytester.path, 'remote-bundles'))

    # Run the test, asserting that one test passes and none fail (implicit)
    pytester.runpytest().assert_outcomes(passed=1)


def test_writefile_file(shell_helper):
    shell_helper.writefile('setup.py')


def test_writefile_from_string(shell_helper):
    shell_helper.writefile('some.txt', 'some stuff in a file')


def test_make_module_fail(shell_helper):
    with pytest.raises(ValueError):
        shell_helper.make_module('/abs/not/okay')


def test_make_module(shell_helper):
    shell_helper.make_module('my/good/module')
    shell_helper.sh('python -c "import my.good.module"')


def test_copy_file(shell_helper):
    assert shell_helper.copy('setup.py', 'target').startswith(shell_helper.testdir)


def test_copy_dir(shell_helper):
    assert shell_helper.copy('tests', 'more-tests').startswith(shell_helper.testdir)
