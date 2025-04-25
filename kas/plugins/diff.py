# kas - setup tool for bitbake based projects
#
# Copyright (c) Siemens, 2025
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
"""
    This plugin implements the ``kas diff`` command.

    This plugin compares two KAS configurations and outputs the
    differences. The diff includes both content differences in
    the configuration files and repository differences if commit
    IDs or tags have changed.

    Additionally, you can use the `--json` option to output the
    diff in JSON format.
"""

import json
from kas.context import create_global_context
from kas.config import Config
from kas.libcmds import Macro
from kas.libkas import setup_parser_common_args

__license__ = 'MIT'
__copyright__ = 'Copyright (c) Siemens, 2025'


class Diff:
    """
    kas plugin to compute diff of two kas configurations.
    """

    name = 'diff'
    helpmsg = (
        'Compare two KAS configurations.'
    )

    @classmethod
    def setup_parser(cls, parser):
        setup_parser_common_args(parser)

        parser.add_argument('config1',
                            help='The first config file to be compared.')
        parser.add_argument('config2',
                            help='The second config file to be compared.')
        parser.add_argument('--json',
                            action='store_true',
                            help='Print diff output in JSON format.')
        parser.add_argument('--oneline',
                            action='store_true',
                            help='Use git oneline output for differing '
                                 'commits.')
        parser.add_argument('--no-color',
                            action='store_true',
                            help='Disable colored highlighting of diffs.')
        parser.add_argument('--commit-only',
                            action='store_true',
                            help='This will not display the differences in '
                                 'the KAS configurations; it will only list '
                                 'commits resulting from different '
                                 'repository revisions.')
        parser.add_argument('--content-only',
                            action='store_true',
                            help='This will only display the differences in '
                                 'the KAS configurations and will not '
                                 'include repository differences.')

    @staticmethod
    def compare_dicts(dict1, dict2, parent_key=''):
        """
        Deep compare dictionaries. Returns a dictionary with the differences.
        """
        diff = {"values_changed": {}}

        def add_change(key, old_value, new_value):
            diff["values_changed"][key] = {
                "old_value": old_value,
                "new_value": new_value
            }

        def deep_compare(d1, d2, parent_key):
            keys = set(d1.keys()).union(set(d2.keys()))
            for key in keys:
                full_key = f"{parent_key}.{key}" if parent_key else key
                if key in d1 and key in d2:
                    if isinstance(d1[key], dict) and isinstance(d2[key], dict):
                        deep_compare(d1[key], d2[key], full_key)
                    elif d1[key] != d2[key]:
                        add_change(full_key, d1[key], d2[key])
                elif key in d1:
                    add_change(full_key, d1[key], None)
                else:
                    add_change(full_key, None, d2[key])

        deep_compare(dict1, dict2, parent_key)
        return diff

    @staticmethod
    def formatting_diff_output(oldfile, newfile, diff_output, oneline,
                               no_color, commit_only, content_only):
        """
        Format the diff output.
        """
        if no_color:
            COLORS_OLD = ''
            COLORS_NEW = ''
            COLORS_COMIT = ''
            COLORS_FILES = ''
            COLORS_ENDC = ''
        else:
            COLORS_OLD = '\033[31m'
            COLORS_NEW = '\033[32m'
            COLORS_COMIT = '\033[33m'
            COLORS_FILES = '\033[34m'
            COLORS_ENDC = '\033[0m'
        prefix_old = "-"
        prefix_new = "+"
        format_dict = {'old_value':
                       {'color': COLORS_OLD, 'prefix': prefix_old},
                       'new_value':
                       {'color': COLORS_NEW, 'prefix': prefix_new}}
        print(f"kas diff {oldfile} {newfile}")
        print(prefix_old * 3, f" {oldfile}")
        print(prefix_new * 3, f" {newfile}")
        for key in diff_output:
            if key == 'values_changed':
                if commit_only:
                    continue
                print(f"{COLORS_FILES}@@ config changed @@{COLORS_ENDC}")
                for key2 in diff_output[key]:
                    for k, i in format_dict.items():
                        value = diff_output[key][key2][k]
                        if value:
                            if '\n' in value:
                                print(f"{i['color']}"
                                      f"{i['prefix']}{' ' * 4}{key2}: "
                                      f"{COLORS_ENDC}")
                                lines = value.splitlines()
                                for line in lines:
                                    print(f"{i['color']}"
                                          f"{i['prefix']}{' ' * 8}{line}"
                                          f"{COLORS_ENDC}")
                            else:
                                print(f"{i['color']}"
                                      f"{i['prefix']}{' ' * 4}{key2}: {value}"
                                      f"{COLORS_ENDC}")
                        else:
                            print(f"{i['color']}"
                                  f"{i['prefix']}{' ' * 4}{key2}: None"
                                  f"{COLORS_ENDC}")
            else:
                if content_only:
                    continue
                print(f"{COLORS_FILES}@@ {key} commits diff @@{COLORS_ENDC}")
                for li in diff_output[key]:
                    msg = li['message']
                    if oneline:
                        msg = msg.split('\n')[0]
                        print(f"{COLORS_COMIT}"
                              f"{li['commit'][:7]} {msg}"
                              f"{COLORS_ENDC}")
                    else:
                        print(f"{COLORS_COMIT}{li['commit']}: {COLORS_ENDC}"
                              f"{li['author']} {li['commit_date']}")
                        indented_msg = '\n'.join([' ' * 4 + s
                                                 for s in msg.split('\n')])
                        print(indented_msg)
            if key != list(diff_output.keys())[-1]:
                print("---")

    def run(self, args):
        args.skip += [
            'setup_environ',
            'write_bbconfig'
        ]
        ctx = create_global_context(args)
        ctx.config = Config(ctx, args.config1)
        macro = Macro()
        macro.run(ctx, args.skip)
        config1 = ctx.config.get_config(remove_includes=True)
        repos1 = ctx.config.get_repos()

        args.skip += [
            'setup_dir',
            'setup_home',
            'setup_ssh_agent'
        ]
        ctx.config = Config(ctx, args.config2)
        macro.run(ctx, args.skip)
        config2 = ctx.config.get_config(remove_includes=True)
        repos2 = ctx.config.get_repos()

        diff = Diff.compare_dicts(config1, config2)
        diff_output = {}
        if diff:
            # combine the diff output and the repo diff to a dict
            diff_output.update(diff)

            # check for commit IDs/tags of repos and compare them
            for key in diff.get('values_changed', {}):
                if 'commit' in key or 'tag' in key:
                    commit1 = diff['values_changed'][key]['old_value']
                    commit2 = diff['values_changed'][key]['new_value']
                    # we do not known which config contains the latest commit,
                    # so we need to check both configs
                    for each_repo in repos1:
                        if each_repo.path and each_repo.name in key:
                            repo_diff = each_repo.diff(commit2, commit1)
                            if len(repo_diff.get(each_repo.name)) > 0:
                                diff_output.update(repo_diff)

                    for each_repo in repos2:
                        if each_repo.path and each_repo.name in key:
                            repo_diff = each_repo.diff(commit1, commit2)
                            if len(repo_diff.get(each_repo.name)) > 0:
                                diff_output.update(repo_diff)
        if args.json:
            print(json.dumps(diff_output, indent=4))
        else:
            Diff.formatting_diff_output(args.config1, args.config2,
                                        diff_output, args.oneline,
                                        args.no_color, args.commit_only,
                                        args.content_only)


__KAS_PLUGINS__ = [Diff]
