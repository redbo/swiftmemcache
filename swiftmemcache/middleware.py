# This is derived from the memcached middleware in Openstack Swift
# Copyright (c) 2010-2012 OpenStack, LLC.

import os
from ConfigParser import ConfigParser, NoSectionError, NoOptionError

from swiftmemcache.client import MemcacheRing


class MemcacheMiddleware(object):
    """
    Caching middleware that manages caching in swift.
    """

    def __init__(self, app, conf):
        self.app = app
        memcache_servers = conf.get('memcache_servers')
        username = conf.get('username')
        password = conf.get('password')

        if not memcache_servers or serialization_format is None:
            path = os.path.join(conf.get('swift_dir', '/etc/swift'),
                                'memcache.conf')
            memcache_conf = ConfigParser()
            if memcache_conf.read(path):
                try:
                    memcache_servers = \
                        memcache_conf.get('memcache', 'memcache_servers')
                except (NoSectionError, NoOptionError):
                    pass
                try:
                    username = memcache_conf.get('memcache', 'username')
                except (NoSectionError, NoOptionError):
                    pass
                try:
                    password = memcache_conf.get('memcache', 'password')
                except (NoSectionError, NoOptionError):
                    pass

        if not memcache_servers:
            memcache_servers = '127.0.0.1:11211'

        self.memcache = MemcacheRing(
            [s.strip() for s in memcache_servers.split(',') if s.strip()],
            username=username,
            password=password)

    def __call__(self, env, start_response):
        env['swift.cache'] = self.memcache
        return self.app(env, start_response)


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def cache_filter(app):
        return MemcacheMiddleware(app, conf)

    return cache_filter
