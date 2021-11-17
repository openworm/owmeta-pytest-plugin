from contextlib import contextmanager
from collections import namedtuple
from subprocess import check_output, CalledProcessError
from os.path import join as p, exists, split as split_path, isdir, isabs
from textwrap import dedent
import tempfile
import shutil
import shlex
import os

from owmeta_core.command import OWM
from owmeta_core.command_util import DEFAULT_OWM_DIR
from owmeta_core.bundle import (find_bundle_directory, AccessorConfig, Remote, Fetcher,
                                retrieve_remote_by_name)
from owmeta_core.bundle.exceptions import BundleNotFound
from owmeta_core.bundle.loaders import Loader
from pkg_resources import resource_stream
from pytest import fixture, mark


__version__ = '0.0.6'

BundleData = namedtuple('BundleData', ('id', 'version', 'source_directory', 'remote'))
TEST_BUNDLES_DIRECTORY = os.environ.get('TEST_BUNDLES_DIRECTORY', 'bundles')


def bundle_fixture_helper(bundle_id, version=None):
    '''
    Creates test fixtures for testing with pre-made bundles.

    See :ref:`usage` in the docs for details.

    Parameters
    ----------
    bundle_id : str
        The ID of the bundle
    version : int, optional
        The version of the bundle

    Returns
    -------
    function
        A function to pass to `pytest.fixture`
    '''
    def bundle(request):
        # Raises a BundleNotFound exception if the bundle can't be found
        nonlocal version, bundle_id
        if bundle_id is None and version is None:
            try:
                bundle_id, version = request.param
            except AttributeError as e:
                raise Exception('Use the bundles decorator to declare bundle'
                        ' versions for this test') from e
        elif version is None:
            try:
                version = request.param
            except AttributeError as e:
                raise Exception('Use the bundle_versions decorator to declare bundle'
                        ' versions for this test') from e

        remotes = []
        marker = request.node.get_closest_marker("bundle_remote")
        remote_defined = False
        test_bundles_remote = marker.args[0] if marker else None
        if test_bundles_remote:
            # If there is a Remote defined, try to read it in, either as the file
            # containing the definition for the Remote...
            try:
                with open(test_bundles_remote) as inp:
                    remote = Remote.read(inp)
            except FileNotFoundError:
                # ...or, if we do not find a file with that name, as the name of a previously
                # configured remote in this project's .owm directory
                remote = retrieve_remote_by_name(p(DEFAULT_OWM_DIR, 'remotes'), test_bundles_remote)
                if remote:
                    remote_defined = True
                    remotes.append(remote)
            else:
                remote_defined = True

        TestBundleLoader = None
        try:
            source_directory = find_bundle_directory(TEST_BUNDLES_DIRECTORY, bundle_id, version)
        except BundleNotFound:
            if not remote_defined:
                raise
            # Set source_directory to None since it is not really applicable in the case
            # that the bundle is not maintained statically in the project
            source_directory = None
        else:
            class TestAC(AccessorConfig):
                def __eq__(self, other):
                    return other is self

                def __hash__(self):
                    return object.__hash__(self)

            class TestBundleLoader(Loader):
                def __init__(self, ac):
                    pass

                def bundle_versions(self):
                    return [version]

                @classmethod
                def can_load_from(cls, ac):
                    if isinstance(ac, TestAC):
                        return True
                    return False

                def can_load(self, ident, version):
                    return ident == bundle_id and version == version

                def load(self, ident, version):
                    shutil.copytree(source_directory, self.base_directory)
            TestBundleLoader.register()
            remote = Remote(f'test_{request.fixturename}', (TestAC(),))
            remotes.append(remote)

        yield BundleData(
                bundle_id,
                version,
                source_directory,
                remotes)
        if TestBundleLoader:
            TestBundleLoader.unregister()
    return bundle


bundle = fixture(bundle_fixture_helper(None))
'''
A fixture for bundles.
'''


def bundles(versions):
    '''
    Parameterize the `bundle` fixture with bundle IDs and versions to test against

    Parameters
    ----------
    versions : list of int
        Versions of the bundle to test against
    '''
    return mark.parametrize('bundle', versions,
            ids=[f'{bundle_id}@{version}' for bundle_id, version in versions], indirect=True)


def bundle_versions(fixture_name, versions):
    '''
    Parameterize a bundle fixture with versions of the bundle to test against

    Parameters
    ----------
    fixture_name : str
        The name of the fixture to parameterize
    versions : list of int
        Versions of the bundle to test against
    '''
    return mark.parametrize(fixture_name, versions,
            ids=[f'{fixture_name}@{v}' for v in versions], indirect=True)


@fixture
def owm_project_with_customizations(request):
    '''
    Factory for an `owm_project` context manager. Accepts a `customizations` argument, the
    same as `shell_helper_with_customizations`.
    '''
    return contextmanager(_owm_project_helper(request))


@fixture
def owm_project(request):
    '''
    Returns a `shell_helper` fixture but with a .owm project directory in the test
    directory. The helper also gets new methods:

    ``owm(**kwargs)``: Creates and returns an `~owmeta_core.command.OWM` with its
    `~owmeta_core.command.OWM.owmdir` at the test .owm directory

    ``fetch(bundle_data)``: Fetches a bundle into the test home directory. `bundle_data`
    likely comes from a test fixture created with `bundle_fixture_helper`

    '''
    with contextmanager(_owm_project_helper(request))() as f:
        yield f


def _owm_project_helper(request):
    def f(*args, **kwargs):
        res = _shell_helper(request, *args, **kwargs)
        try:
            default_context_id = 'http://example.org/data'
            res.sh(f'owm -b init --default-context-id "{default_context_id}"')

            res.owmdir = p(res.testdir, DEFAULT_OWM_DIR)
            res.default_context_id = default_context_id

            def owm(userdir=None, **kwargs):
                if 'owmdir' not in kwargs:
                    kwargs['owmdir'] = res.owmdir
                r = OWM(**kwargs)
                if userdir:
                    r.userdir = userdir
                else:
                    r.userdir = p(res.test_homedir, '.owmeta')
                return r

            def fetch(bundle_data):
                bundles_directory = p(res.test_homedir, '.owmeta', 'bundles')
                fetcher = Fetcher(bundles_directory, bundle_data.remote)
                return fetcher.fetch(bundle_data.id, bundle_data.version)

            res.owm = owm
            res.fetch = fetch

            yield res
        finally:
            shutil.rmtree(res.testdir)
    return f


@fixture
def shell_helper(request):
    '''
    Helper for running shell commands from a temporary working directory and home
    directory. Returns a `.Data` instance.
    '''
    res = _shell_helper(request)
    try:
        yield res
    finally:
        shutil.rmtree(res.testdir)


@fixture
def shell_helper_with_customizations(request):
    '''
    Like `shell_helper`, but returns a context manager instead which accepts a
    `customizations` argument, a string that will be written as the contents of
    :file:`sitecustomize.py` to be picked up for any executions of `~Data.sh`
    '''
    @contextmanager
    def f(*args, **kwargs):
        res = _shell_helper(request, *args, **kwargs)
        try:
            yield res
        finally:
            shutil.rmtree(res.testdir)
    return f


def _shell_helper(request, customizations=None):
    res = Data()
    os.mkdir(res.test_homedir)

    # Am I *supposed* to use _cov to detect pytest-cov installation? Maybe... maybe
    # not....
    pm = request.config.pluginmanager
    if pm.hasplugin('_cov'):
        with resource_stream('owmeta_pytest_plugin', 'pytest-cov-embed.py') as f:
            ptcov = f.read()
        # Added so pytest_cov gets to run for our subprocesses
        with open(p(res.testdir, 'sitecustomize.py'), 'wb') as f:
            f.write(ptcov)
            f.write(b'\n')

    def apply_customizations():
        if customizations:
            with open(p(res.testdir, 'sitecustomize.py'), 'a') as f:
                f.write(dedent(customizations))

    res.apply_customizations = apply_customizations
    return res


@fixture(scope='session', autouse=True)
def owmeta_ep_cache():
    with tempfile.TemporaryDirectory(prefix=f'{__name__}.ep_cache.') as tempdir:
        os.environ['OWMETA_EP_CACHE_LOCATION'] = tempdir
        yield


class Data(object):
    '''
    Object returned by `shell_helper` and `owm_project` (and related fixtures). Additional
    standard attributes may be added by the various fixtures.

    Attributes
    ----------
    testdir : str
        The temporary directory used for the CWD for `sh`
    test_homedir : str
        The temporary home directory for executions of `sh`
    '''

    exception = None

    def __init__(self):
        self.testdir = tempfile.mkdtemp(prefix=__name__ + '.')
        self.test_homedir = p(self.testdir, 'homedir')

    def __str__(self):
        items = []
        for m in vars(self):
            if (m.startswith('_') or m == 'sh'):
                continue
            items.append(m + '=' + repr(getattr(self, m)))
        return 'Data({})'.format(', '.join(items))

    def copy(self, source, dest):
        '''
        Copy files / directory tries into the test directory

        Parameters
        ----------
        source : str
            Source file or directory
        dest : str
            Target directory. Will be interpreted relative to `testdir`
        '''
        if isdir(source):
            return shutil.copytree(source, p(self.testdir, dest))
        else:
            return shutil.copy(source, p(self.testdir, dest))

    def make_module(self, module):
        '''
        Create a module directory under `testdir`. Each of the intermediate directories
        (if there are any) will also be usable as modules (i.e., they'll have __init__.py
        files in them).

        Parameters
        ----------
        module : str
            Path to the module directory. Must be a relative path

        Returns
        -------
        str
            The full path to the module directory
        '''
        if isabs(module):
            raise ValueError('Must use a relative path. Given ' + str(module))
        modpath = p(self.testdir, module)
        os.makedirs(modpath)
        last_dname = None
        dname = modpath
        while last_dname != dname and dname != self.testdir:
            open(p(dname, '__init__.py'), 'x').close()
            base = ''
            while not base and last_dname != dname:
                last_dname = dname
                dname, base = split_path(modpath)

        return modpath

    def writefile(self, name, contents=None):
        '''
        Write a file to the test directory

        Parameters
        ----------
        name : str
            Path name for the file to write
        contents : str
            File name of a file to read from for the content or the literal string
            contents to write to the file

        Returns
        -------
        str
            Full path to the written file
        '''
        if contents is None:
            contents = name
        fname = p(self.testdir, name)
        with open(fname, 'w') as f:
            if exists(contents):
                print(open(contents).read(), file=f)
            else:
                print(dedent(contents), file=f)
            f.flush()
        return fname

    def sh(self, *command, **kwargs):
        '''
        Execute commands with the working directory set to `testdir`, the
        :envvar:`HOME` environment variable set to `test_homedir`, and with `testdir`
        prepended to :envvar:`PYTHONPATH`.

        Parameters
        ----------
        *command : list of str
            Command or commands to execute
        **kwargs : dict
            Additional arguments to `subprocess.check_output`

        Returns
        -------
        str or list of str
            Output of the given command. See `subprocess.check_output` for details on
            return values and how they are affected by arguments to that function.
        '''
        if not command:
            return None
        env = dict(os.environ)
        env['PYTHONPATH'] = self.testdir + ((os.pathsep + env['PYTHONPATH'])
                                            if 'PYTHONPATH' in env
                                            else '')
        env['HOME'] = self.test_homedir
        env.update(kwargs.pop('env', {}))
        outputs = []
        for cmd in command:
            try:
                outputs.append(check_output(shlex.split(cmd), env=env, cwd=self.testdir, **kwargs).decode('utf-8'))
            except CalledProcessError as e:
                if e.output:
                    print(dedent('''\
                    ----------stdout from "{}"----------
                    {}
                    ----------{}----------
                    ''').format(cmd.strip(), e.output.decode('UTF-8'),
                               'end stdout'.center(14 + len(cmd))))
                if getattr(e, 'stderr', None):
                    print(dedent('''\
                    ----------stderr from "{}"----------
                    {}
                    ----------{}----------
                    ''').format(cmd.strip(), e.stderr.decode('UTF-8'),
                               'end stderr'.center(14 + len(cmd))))
                raise
        return outputs[0] if len(outputs) == 1 else outputs

    __repr__ = __str__


def pytest_configure(config):
    config.addinivalue_line('markers',
            'bundle_remote: Declares a serialized remote to use in testing')
