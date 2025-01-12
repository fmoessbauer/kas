# SPDX-License-Identifier: MIT
# SPDX-Copyright-Notice: Copyright 2024 Siemens AG
#
# Author: Felix Moessbauer <felix.moessbauer@siemens.com>
#
# Convert a repo manifest XML file to a kas YAML file
# Example:
#  repoManifest2kasYml.py default.xml > kas.yml
#  kas checkout kas.yml
#  run setup script
#  repoManifestStep2.py kas.yml <builddir> > kas-final.yml
#  kas build kas-final.yml

from oelint_parser.cls_stash import Stash
from oelint_parser.cls_item import Variable
import regex as re
from pathlib import Path
import sys
import yaml


def extract_layer(layer):
    layer = re.sub(r'^\${.*?}/', '', layer)
    return Path(layer)


def vars_to_block(vars):
    return '\n'.join([f'{k}="{v}"' for k, v in vars.items()])


def sanitize_var(var):
    return var.strip('"').strip("'")


if len(sys.argv) < 3:
    print(f'Usage: {sys.argv[0]} <config> <builddir>')
    sys.exit(1)

conffile = Path(sys.argv[1])
builddir = Path(sys.argv[2])

# create an stash object
_stash = Stash(quiet=True)

# add any bitbake like file
conf_files = ['site.conf', 'auto.conf', 'local.conf', 'bblayers.conf']
for cf in conf_files:
    if (builddir / f'conf/{cf}').exists():
        _stash.AddFile(builddir / f'conf/{cf}')
_stash.Finalize()

layers_raw = []
conf_vars = {
    'site': {},
    'auto': {},
    'local': {},
    'bblayers': {},
}

for x in _stash.GetItemsFor(attribute=Variable.ATTR_VAR):
    file = Path(x.Origin).name
    if x.VarName == 'MACHINE' and file == 'local.conf':
        MACHINE = sanitize_var(x.get_items()[0])
    elif x.VarName == 'DISTRO' and file == 'local.conf':
        DISTRO = sanitize_var(x.get_items()[0])
    elif file == 'local.conf' and x.VarName in ['BBMULTICONFIG', 'DL_DIR']:
        continue
    elif file == 'site.conf':
        conf_vars['site'][x.VarName] = x.get_items()[0]
    elif file == 'auto.conf':
        conf_vars['auto'][x.VarName] = x.get_items()[0]
    elif file == 'local.conf':
        conf_vars['local'][x.VarName] = x.get_items()[0]
    elif file == 'bblayers.conf':
        if x.VarName in ['BBPATH', 'BBFILES']:
            continue
        if x.VarName == 'BBLAYERS':
            layers_raw += [_stash.ExpandTerm(x.Origin, item)
                           for item in x.get_items()]
            continue
        conf_vars['bblayers'][x.VarName] = x.get_items()[0]
    else:
        print(f'Unknown variable: {x.VarName} in {file}', file=sys.stderr)

# deduplicate but keep order
layers = list(dict.fromkeys([extract_layer(x) for x in layers_raw]))

conf = yaml.safe_load(conffile.read_text())
conf['machine'] = MACHINE
conf['distro'] = DISTRO
conf['local_conf_header'] = {
    '00_site': vars_to_block(conf_vars['site']),
    '01_auto': vars_to_block(conf_vars['auto']),
    '02_local': vars_to_block(conf_vars['local'])
}
conf['bblayers_conf_header'] = {
    '00_bblayers': vars_to_block(conf_vars['bblayers'])
}

for name, repo in conf['repos'].items():
    rpath = Path(repo['path'])
    print(f'Repo {name} with path {rpath}: add layers', file=sys.stderr)
    for layer in layers:
        if layer == rpath:
            print('  Repo is added as layer', file=sys.stderr)
            conf['repos'][name]['layers']['.'] = None
        elif layer.is_relative_to(rpath):
            layerpath = layer.relative_to(rpath)
            print(f'  Add layer {layerpath}', file=sys.stderr)
            conf['repos'][name]['layers'][str(layerpath)] = None
    if 'linkfiles' in repo:
        del conf['repos'][name]['linkfiles']
yaml.dump(conf, sys.stdout, sort_keys=False)
