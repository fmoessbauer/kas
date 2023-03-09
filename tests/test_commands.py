# kas - setup tool for bitbake based projects
#
# Copyright (c) Konsulko Group, 2020
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import glob
import os
import pathlib
import shutil
import json
import yaml
from kas import kas


def test_for_all_repos(changedir, tmpdir):
    tdir = str(tmpdir / 'test_commands')
    shutil.copytree('tests/test_commands', tdir)
    os.chdir(tdir)
    kas.kas(['for-all-repos', 'test.yml',
             '''if [ -n "${KAS_REPO_URL}" ]; then git rev-parse HEAD \
                     >> %s/ref_${KAS_REPO_NAME}; fi''' % tdir])

    with open('ref_kas_1.0', 'r') as f:
        assert f.readline().strip() \
            == '907816a5c4094b59a36aec12226e71c461c05b77'
    with open('ref_kas_1.1', 'r') as f:
        assert f.readline().strip() \
            == 'e9ca55a239caa1a2098e1d48773a29ea53c6cab2'


def test_checkout(changedir, tmpdir):
    tdir = str(tmpdir / 'test_commands')
    shutil.copytree('tests/test_commands', tdir)
    os.chdir(tdir)
    kas.kas(['checkout', 'test.yml'])

    # Ensure that local.conf and bblayers.conf are populated, check that no
    # build has been executed by ensuring that no tmp, sstate-cache or
    # downloads directories are present.
    assert os.path.exists('build/conf/local.conf')
    assert os.path.exists('build/conf/bblayers.conf')
    assert not glob.glob('build/tmp*')
    assert not os.path.exists('build/downloads')
    assert not os.path.exists('build/sstate-cache')


def test_checkout_create_refs(changedir, tmpdir):
    tdir = str(tmpdir / 'test_commands')
    repo_cache = pathlib.Path(str(tmpdir.mkdir('repos')))
    shutil.copytree('tests/test_patch', tdir)
    os.chdir(tdir)
    os.environ['KAS_REPO_REF_DIR'] = str(repo_cache)
    kas.kas(['checkout', 'test.yml'])
    del os.environ['KAS_REPO_REF_DIR']
    assert os.path.exists(str(repo_cache / 'github.com.siemens.kas.git'))
    assert os.path.exists('kas/.git/objects/info/alternates')


def test_repo_includes(changedir, tmpdir):
    tdir = str(tmpdir / 'test_commands')
    shutil.copytree('tests/test_repo_includes', tdir)
    os.chdir(tdir)
    kas.kas(['checkout', 'test.yml'])


def test_dump(changedir, tmpdir, capsys):
    tdir = str(tmpdir / 'test_commands')
    shutil.copytree('tests/test_repo_includes', tdir)
    os.chdir(tdir)

    formats = ['json', 'yaml']
    resolve = ['', '--resolve-refs', '--resolve-env']
    # test cross-product of these options (formats x resolve)
    for f, r in ((f, r) for f in formats for r in resolve):
        outfile = 'test_flat.%s' % f
        if r == '--resolve-env':
            os.environ['TESTVAR_FOO'] = 'KAS'

        kas.kas(('dump --format %s %s test.yml' % (f, r)).split())

        if r == '--resolve-env':
            del os.environ['TESTVAR_FOO']

        with open(outfile, 'w') as f:
            f.write(capsys.readouterr().out)

        with open(outfile, 'r') as cf:
            flatconf = json.load(cf) if f == 'json' else yaml.safe_load(cf)
            refspec = flatconf['repos']['kas3']['refspec']
            envvar = flatconf['env']['TESTVAR_FOO']
            if r == '--resolve-refs':
                assert refspec != 'master'
            else:
                assert refspec == 'master'
            if r == '--resolve-env':
                assert envvar == 'KAS'
            else:
                assert envvar == 'BAR'

            assert 'includes' not in flatconf['header']
            # check if kas can read the generated file
            if f == 'yaml':
                shutil.rmtree('%s/build' % tdir, ignore_errors=True)
                kas.kas(('checkout %s' % outfile).split())
                assert os.path.exists('build/conf/local.conf')


def test_lockfile(changedir, tmpdir, capsys):
    tdir = str(tmpdir.mkdir('test_commands'))
    shutil.rmtree(tdir, ignore_errors=True)
    shutil.copytree('tests/test_repo_includes', tdir)
    os.chdir(tdir)

    # no lockfile yet, branches are floating
    kas.kas('dump test.yml'.split())
    rawspec = yaml.safe_load(capsys.readouterr().out)
    assert rawspec['repos']['externalrepo']['refspec'] == 'master'

    # create lockfile
    kas.kas('dump --lock --inplace test.yml'.split())
    assert os.path.exists('test.lock.yml')

    # lockfile is considered during import, expect pinned branches
    kas.kas('dump test.yml'.split())
    lockspec = yaml.safe_load(capsys.readouterr().out)
    assert lockspec['overrides']['repos']['externalrepo']['refspec'] \
        != 'master'

    # insert older refspec into lockfile (kas 3.2 tag)
    test_refspec = 'dc44638cd87c4d0045ea2ca441e682f3525d8b91'
    lockspec['overrides']['repos']['externalrepo']['refspec'] = test_refspec
    with open('test.lock.yml', 'w') as f:
        yaml.safe_dump(lockspec, f)

    # check if repo is moved to specified commit
    kas.kas('dump test.yml'.split())
    lockspec = yaml.safe_load(capsys.readouterr().out)
    assert lockspec['overrides']['repos']['externalrepo']['refspec'] \
        == test_refspec

    # update lockfile, check if repo is pinned to other commit
    kas.kas('dump --lock --inplace --update test.yml'.split())
    with open('test.lock.yml', 'r') as f:
        lockspec = yaml.safe_load(f)
        assert lockspec['overrides']['repos']['externalrepo']['refspec'] \
            != test_refspec
