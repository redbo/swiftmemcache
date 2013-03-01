Memcache client and middleware for Swift that is able to do SASL auth.
It requires eventlet and pure\_sasl

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
