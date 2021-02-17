.. _usage:

Fixture Usage
=============

bundle_fixture_helper
---------------------
`~owmeta_pytest_plugin.bundle_fixture_helper` may be used for testing against
older versions of bundles maintained within the project or for creating a "test
fake" of a bundle dependency to test integration short of fetching the full
dependency. `bundle_fixture_helper` is used for *making* fixtures that provide
these bundles. For example::

    import pytest

    my_bundle_23 = pytest.fixture(bundle_fixture_helper('example/my_bundle', 23))

The fixture provides a `remote <owmeta_core.bundle.Remote>` with one accessor
just for the bundle under test. The bundles are retrieved from a source
directory by the `~owmeta_pytest_plugin.owm_project` fixture with the `fetch`
method of that fixture::

    def test_my_bundle(my_bundle_23, owm_project):
        # Fetch the bundle into test-scoped bundle cache directory 
        owm_project.fetch(my_bundle_23)
        # Do other stuff with the bundle

The source directory for the bundles follows the same structure as the bundle
cache directory in :file:`~/.owmeta/bundles`. The location for the directory
comes from the :envvar:`TEST_BUNDLES_DIRECTORY` environment variable and
defaults to :file:`bundles` in the current working directory if that variable
is unset. It is *not* recommended to include the indexed database files, whose
names start with `"owm.db" <owmeta_core.bundle.common.BUNDLE_INDEXED_DB_NAME>`,
in the source bundles as they will be created by `owm_project.fetch` where
needed.

Typically, for bundles carrying full data sets as opposed to bundles only
carrying schemas, you will want to store the bundle outside of your source
tree. To do this you can declare the `remote <owmeta_core.bundle.Remote>` from
which the bundles can be fetched, typically by using the `owm bundle remote add
<owmeta_core.commands.bundle.OWMBundleRemoteAdd>` command, something like this::

    $ owm bundle remote add ex http://example.org/bundle/remote

Then you can declare the remote with the `bundle_remote` marker. For example::

    from pathlib import Path

    @pytest.mark.bundle_remote('ex')
    def test_my_bundle_remote(my_bundle_23, owm_project):
        # Fetch the bundle into test-scoped bundle cache directory 
        owm_project.fetch(my_bundle_23)

If the `version` argument to `bundle_fixture_helper` is omitted, then the
version numbers will come from parameters, typically provided by
:ref:`pytest.mark.paremetrize<parametrizemark>`.
`~owmeta_pytest_plugin.bundle_versions` creates a parametrize marker for this
purpose. For example::

    from owmeta_pytest_plugin import bundle_versions, bundles

    my_bundle = pytest.fixture(bundle_fixture_helper('example/my_bundle'))

    @bundle_versions('my_bundle', list(range(1, 5)))
    def test_my_bundle(my_bundle):
        # do something with my_bundle

In addition, if you want to test against multiple bundles, not necessarily with
the same ID (e.g., if you change your bundle's ID at some point), then you can
use `~owmeta_pytest_plugin.bundles`::

    @bundles([('example/aBundle', 1),
              ('_orphans/aBundle', 2),
              ('phoenix/aBundle', 3),])
    def test_bundle_with_renames(bundle, owm_project):
        owm_project.fetch(bundle)
        # do something with the current version of aBundle

This also demonstrates the use of the `~owmeta_pytest_plugin.bundle` fixture,
which is just a variant of what `bundle_fixture_helper` produces.
