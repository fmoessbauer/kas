# kas - setup tool for bitbake based projects
#
# Copyright (c) Siemens AG, 2025
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
Example to show how to write external kas plugins
"""

__license__ = 'MIT'
__copyright__ = 'Copyright (c) Siemens AG, 2025'

from kas.libkas import setup_parser_common_args


class HelloWorld:
    """
    This plugin implements the ``kas hello-world`` command.
    When this command is executed, kas will print a hello world message.
    The following is the bare-minimum required to implement a kas plugin:
    - name: Name of the sub command to run the plugin
    - helpmsg: Help message that is displayed when the user runs ``kas -h``.
    - setup_parser: Setup the sub-parser of this plugin.
    - run: Method that is called when executing the plugin.
    """
    name = 'hello-world'
    helpmsg = (
        'Prints a hello world message'
    )

    @classmethod
    def setup_parser(cls, parser):
        setup_parser_common_args(parser)

    def run(self, args):
        print('Hello, world!')
