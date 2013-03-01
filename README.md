This is a pure python memcache client that supports SASL auth.

It includes middleware to easily drop it into Openstack Swift, though there's
nothing else Swift-specific in the client.

It has no dependencies (though it will try to import eventlet.socket and
simplejson, falling back on stdlib socket and json).

You can set a username and password in the filter section of your proxy config
when you add the middleware, or to your /etc/swift/memcached.conf if you swing
that way.

    [filter:cache2]
    use = egg:swiftmemcache#swift_middleware
    username = user
    password = pass

Alternatively, you can define a username and password per server.

    [filter:cache2]
    use = egg:swiftmemcache#swift_middleware
    memcache_servers = 'user:pass@127.0.0.1:11211'
