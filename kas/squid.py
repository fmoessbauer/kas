# kas - setup tool for bitbake based projects
#
# Copyright (c) Siemens AG, 2017-2024
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
    This module contains the classes to setup and run Squid.
"""

import os
import shutil
import subprocess
import logging
import tempfile
from urllib.parse import urlparse
from kas.libcmds import Command

# override expiry time of .deb (redirect) urls to 3 days
DEBIAN_SNAPSHOT_DEB_EXPIRE = 60 * 24 * 3
CACHE_SIZE_MB = 5000


class SquidConfig:
    def __init__(self,
                 cache_dir: str,
                 log_dir: str,
                 http_proxy: str = None,
                 debian_snapshot: bool = False,
                 debian_snapshot_rate_kb: int = 0):
        self.cache_dir = cache_dir
        self.log_dir = log_dir
        self.http_port = 3128
        self.debian_snapshot = debian_snapshot
        self.debian_snapshot_rate = debian_snapshot_rate_kb * 1024
        self.upstream_proxy_host = None
        self.upstream_proxy_port = None
        self.base_config = '''acl SSL_ports port 443
acl Safe_ports port 80		# http
acl Safe_ports port 21		# ftp
acl Safe_ports port 443		# https
acl Safe_ports port 70		# gopher
acl Safe_ports port 210		# wais
acl Safe_ports port 1025-65535	# unregistered ports
acl Safe_ports port 280		# http-mgmt
acl Safe_ports port 488		# gss-http
acl Safe_ports port 591		# filemaker
acl Safe_ports port 777		# multiling http
acl CONNECT method CONNECT
http_access deny !Safe_ports
http_access deny CONNECT !SSL_ports
http_access deny manager
http_access allow localhost
http_access deny all
maximum_object_size 1024 MB
shutdown_lifetime 0 seconds
pid_filename none
'''
        self.debian_snapshot_config = '''
acl DEBIAN-SNAPSHOT dstdomain snapshot.debian.org
delay_pools 1
delay_class 1 1
delay_access 1 allow DEBIAN-SNAPSHOT
delay_access 1 deny all
'''

        if http_proxy:
            proxy = urlparse(http_proxy)
            self.upstream_proxy_host = proxy.hostname
            self.upstream_proxy_port = proxy.port
        if self.upstream_proxy_port == self.http_port and \
                self.upstream_proxy_host == 'localhost':
            logging.debug('Squid upstream proxy is the same as the '
                          'internal proxy, incrementing port')
            self.http_port += 1

    def write(self, file):
        file.write(self.base_config)
        file.write(f'http_port {self.http_port}\n')
        file.write(f'cache_dir ufs {self.cache_dir} {CACHE_SIZE_MB} 16 256\n')
        file.write(f'cache_log stdio:{self.log_dir}/cache.log\n')
        file.write(f'access_log stdio:{self.log_dir}/access.log\n')
        if self.upstream_proxy_host:
            file.write(f'cache_peer {self.upstream_proxy_host} '
                       f'parent {self.upstream_proxy_port} '
                       '7 no-query default\n')
        if self.debian_snapshot:
            limit = self.debian_snapshot_rate
            if limit:
                file.write(self.debian_snapshot_config)
                file.write(f'delay_parameters 1 {limit}/{limit}\n')
            exp = DEBIAN_SNAPSHOT_DEB_EXPIRE
            file.write('refresh_pattern snapshot.debian.org\\/.*\\.deb$ '
                       f'{exp} 100% {exp} ignore-reload ignore-no-store '
                       'override-expire\n')


class SquidInstance:
    def __init__(self, cfgfile, handle):
        self.cfgfile = cfgfile
        self.handle = handle


class SetupSquid(Command):
    def __str__(self) -> str:
        return 'setup_squid'

    def execute(self, ctx):
        squid_tool = "/usr/sbin/squid"
        if shutil.which(squid_tool) is None:
            raise RuntimeError('squid setup requested but could '
                               f'not find "{squid_tool}"')

        squid_conf = SquidConfig(
            cache_dir=ctx.build_dir + '/squid-cache/cache',
            log_dir=ctx.build_dir + '/squid-cache/logs',
            http_proxy=ctx.environ.get('http_proxy'),
            debian_snapshot=ctx.config.get_build_system() == 'isar',
            debian_snapshot_rate_kb=ctx.args.squid_snapshot_rate or 0)

        with tempfile.NamedTemporaryFile(mode='w', prefix="squid.",
                                         delete=False) as temp_file:
            squid_conf_file = temp_file.name
            squid_conf.write(temp_file)

        for d in [squid_conf.cache_dir, squid_conf.log_dir]:
            os.makedirs(d, exist_ok=True)

        subprocess.check_call([squid_tool, '--foreground', '-z',
                               '-f', squid_conf_file],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        squid_handle = subprocess.Popen(
            [squid_tool, '-f', squid_conf_file, '-N'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ctx.squid = SquidInstance(squid_conf_file, squid_handle)
        ctx.environ['http_proxy'] = f'http://localhost:{squid_conf.http_port}'
        logging.info('Providing internal squid proxy on port '
                     f'{squid_conf.http_port}')


class CleanupSquid(Command):
    def __str__(self) -> str:
        return 'cleanup_squid'

    def execute(self, ctx):
        if ctx.squid:
            logging.info('Terminating squid')
            ctx.squid.handle.send_signal(subprocess.signal.SIGTERM)
            ctx.squid.handle.wait()
            os.unlink(ctx.squid.cfgfile)
