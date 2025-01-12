# SPDX-License-Identifier: MIT
# SPDX-Copyright-Notice: Copyright 2024 Siemens AG
#
# Author: Felix Moessbauer <felix.moessbauer@siemens.com>
#
# Convert a repo manifest XML file to a kas YAML file
# Example:
#  repoManifest2kasYml.py default.xml > kas.yml
#  kas checkout kas.yml


import xml.etree.ElementTree as ET
import yaml
import sys
import re

# repo manifest spec
# https://gerrit.googlesource.com/git-repo/+/master/docs/manifest-format.md#Element-default

# TODO: this requires a kas schema addition
LINKFILES_SUPPORTED = True


def get_defaults(el):
    defaults = {
        'remote': None,
        'revision': None,
        'upstream': None
    }
    if len(el) > 1:
        raise ValueError('Too many default elements')

    for child in el:
        if child.tag == 'default':
            defaults['remote'] = child.attrib.get('remote')
            defaults['revision'] = child.attrib.get('revision')
            defaults['upstream'] = child.attrib.get('upstream')
    return defaults


def get_remotes(el):
    remotes = {}
    for child in el:
        if child.tag == 'remote':
            remotes[child.attrib.get('name')] = {
                'fetch': child.attrib.get('fetch'),
                'revision': child.attrib.get('revision')
            }
    return remotes


def get_projects(el):
    projects = {}
    for child in el:
        if child.tag == 'project':
            name = child.attrib.get('name')
            projects[name] = {
                'path': child.attrib.get('path'),
                'remote': child.attrib.get('remote'),
                'revision': child.attrib.get('revision'),
                'upstream': child.attrib.get('upstream'),
            }
            for po in child:
                if po.tag == 'linkfile':
                    if 'linkfiles' not in projects[name]:
                        projects[name]['linkfiles'] = []
                    projects[name]['linkfiles'].append(
                        {'src': po.attrib.get('src'),
                         'dest': po.attrib.get('dest')})
                    continue
                print(f'warning: {po.tag} on "{name}" ignored',
                      file=sys.stderr)
    return projects


def _triage_revision(rev, upstream):
    if rev and re.match(r'^[0-9a-f]{40}|[0-9a-f]{64}$', rev):
        return (rev, None, upstream)
    if rev and rev.startswith('refs/tags/'):
        return (None, rev[11:], upstream)
    return (None, None, rev)


def get_kas_defaults(defaults):
    _, tag, branch = _triage_revision(defaults.get('revision'),
                                      defaults.get('upstream'))
    defaults = {}
    if tag:
        defaults['repos'] = {'tag': tag}
    if branch:
        defaults['repos'] = {'branch': branch}
    return defaults


def get_kas_repos(defaults, remotes, projects):

    repos = {}
    for name, project in projects.items():
        remote = project.get('remote') or defaults.get('remote')
        if not remote:
            raise ValueError(f'No remote specified for project {name}')
        remote_url = remotes[remote]['fetch']
        # only branches can be defaulted, but we don't know if the revision
        # is a branch or a commit (yet)
        revision = project.get('revision') or defaults.get('revision')
        upstream = project.get('upstream')

        if not revision:
            raise ValueError(f'No revision specified for project {name}')
        commit, tag, branch = _triage_revision(revision, upstream)

        repos[name] = {
            'url': f'{remote_url}/{name}',
        }
        path = project.get('path')
        if path:
            repos[name]['path'] = path
        if commit:
            repos[name]['commit'] = commit
            repos[name]['branch'] = None
            repos[name]['tag'] = None
        if tag:
            repos[name]['tag'] = tag
            repos[name]['branch'] = None
        if branch:
            repos[name]['branch'] = branch
            repos[name]['tag'] = None
        # disable importing layers
        repos[name]['layers'] = {'.': False}
        if 'linkfiles' in project and LINKFILES_SUPPORTED:
            repos[name]['linkfiles'] = project['linkfiles']

    return repos


def parseManifestXML(xmlfile):
    '''
    Parse a repo manifest XML file and return a dictionary of the manifest
    with all relevant information.
    '''
    tree = ET.parse(xmlfile)
    root = tree.getroot()

    default = root.findall('default')
    remotes = root.findall('remote')
    projects = root.findall('project')
    # TODO: include manifest support

    manifest = {
        'defaults': get_defaults(default),
        'remotes': get_remotes(remotes),
        'projects': get_projects(projects)
    }
    return manifest


def get_kas_representation(manifest):
    defaults = manifest['defaults']
    remotes = manifest['remotes']
    projects = manifest['projects']

    spec = {
        'header': {'version': 18},
        'defaults': get_kas_defaults(defaults),
        'repos': get_kas_repos(defaults, remotes, projects)
    }

    return spec


if __name__ == '__main__':
    if (len(sys.argv) != 2):
        print('Usage: ' + sys.argv[0] + ' infile')
        sys.exit(0)

    infile = sys.argv[1]

    manifest = parseManifestXML(infile)
    kas = get_kas_representation(manifest)
    yaml.dump(kas, sys.stdout, sort_keys=False)
