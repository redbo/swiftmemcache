This is a pure python memcache client that supports SASL auth (DIGEST-MD5,
CRAM-MD5, PLAIN and LOGIN mechanisms).

It has no dependencies (though it will try to import eventlet.socket and
simplejson, falling back on stdlib socket and json).

It has a fairly simple interface.

```python
from swiftmemcache.client import MemcacheRing

connection = MemcacheRing(['127.0.0.1'], username='user', password='pass')

connection.set('hello', 'world')

print connection.get('hello')
>> world

connection.delete('hello')

print connection.incr('counter', 1)
>> 1

print connection.decr('counter', 1)
>> 0

connection.delete('counter')
```

It json-serializes values and employes rudimentary failure detection and
consistent hashing (sorry, it's a bit opinionated there).

It includes middleware to easily drop it into Openstack Swift.  You can set a
username and password in the filter section of your proxy config when you add
the middleware, or to your /etc/swift/memcached.conf if you swing that way.

    [filter:cache2]
    use = egg:swiftmemcache#swift_middleware
    memcache_servers = 127.0.0.1,127.0.0.2
    username = user
    password = pass

Alternatively, you can define a username and password per server.

    [filter:cache2]
    use = egg:swiftmemcache#swift_middleware
    memcache_servers = user:pass@127.0.0.1
