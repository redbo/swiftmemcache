Memcache client and middleware that supports SASL auth.  This was written for
Openstack Swift, but there's nothing swift-specific in it.

It has no dependencies (though it will try to import eventlet.socket and
simplejson, falling back on stdlib socket and json).

You can set a username and password in the filter section of your proxy config
when you add the middleware, or to your /etc/swift/memcached.conf if you swing
that way.

    [filter:cache2]
    use = egg:swiftmemcache#memcache
    username = user
    password = pass

Alternatively, you can define a username and password per server.

    [filter:cache2]
    use = egg:swiftmemcache#memcache
    memcache_servers = 'user:pass@127.0.0.1:11211'
