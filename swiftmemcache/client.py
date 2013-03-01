# This is derived from the memcached library in Openstack Swift
# Copyright (c) 2010-2012 OpenStack, LLC.

import struct
import logging
import time
from bisect import bisect
from hashlib import md5

try:
    import simplejson as json
except ImportError:
    import json

try:
    from eventlet.green import socket
except ImportError:
    import socket

from swiftmemcache.sasl import SaslAuth


DEFAULT_MEMCACHED_PORT = 11211

CONN_TIMEOUT = 0.3
IO_TIMEOUT = 2.0
JSON_FLAG = 2
NODE_WEIGHT = 50
TRY_COUNT = 3

# if ERROR_LIMIT_COUNT errors occur in ERROR_LIMIT_TIME seconds, the server
# will be considered failed for ERROR_LIMIT_DURATION seconds.
ERROR_LIMIT_COUNT = 10
ERROR_LIMIT_TIME = 60
ERROR_LIMIT_DURATION = 60

MEMCACHE_HEADER = '!BBHBBHIIQ'
MEMCACHE_HEADER_LEN = struct.calcsize(MEMCACHE_HEADER)

STATUS_NO_ERROR = 0x0
STATUS_UNAUTHORIZED = 0x20
STATUS_CONTINUE_AUTH = 0x21
STATUS_UNKNOWN_COMMAND = 0x81

OP_GET = 0x00
OP_SET = 0x01
OP_DELETE = 0x04
OP_INCREMENT = 0x05
OP_DECREMENT = 0x06
OP_SASL_MECHS = 0x20
OP_SASL_REQ = 0x21
OP_SASL_CONTINUE = 0x22


def md5hash(key):
    return md5(key).hexdigest()


class MemcacheConnectionError(Exception):
    pass


class MemcacheRing(object):
    def __init__(self, servers, connect_timeout=CONN_TIMEOUT,
                 io_timeout=IO_TIMEOUT, tries=TRY_COUNT,
                 username=None, password=None):
        self._ring = {}
        self._errors = dict(((serv, []) for serv in servers))
        self._error_limited = dict(((serv, 0) for serv in servers))
        for server in sorted(servers):
            for i in xrange(NODE_WEIGHT):
                self._ring[md5hash('%s-%s' % (server, i))] = server
        self._tries = tries if tries <= len(servers) else len(servers)
        self._sorted = sorted(self._ring.keys())
        self._client_cache = dict(((server, []) for server in servers))
        self._connect_timeout = connect_timeout
        self._io_timeout = io_timeout
        self._username = username
        self._password = password

    def _exception_occurred(self, server, e, action='talking'):
        if isinstance(e, socket.timeout):
            logging.error("Timeout %(action)s to memcached: %(server)s",
                          {'action': action, 'server': server})
        else:
            logging.exception("Error %(action)s to memcached: %(server)s",
                              {'action': action, 'server': server})
        now = time.time()
        self._errors[server].append(time.time())
        if len(self._errors[server]) > ERROR_LIMIT_COUNT:
            self._errors[server] = [err for err in self._errors[server]
                                    if err > now - ERROR_LIMIT_TIME]
            if len(self._errors[server]) > ERROR_LIMIT_COUNT:
                self._error_limited[server] = now + ERROR_LIMIT_DURATION
                logging.error('Error limiting server %s', server)

    def _get_conns(self, key):
        pos = bisect(self._sorted, key)
        served = []
        while len(served) < self._tries:
            pos = (pos + 1) % len(self._sorted)
            server = self._ring[self._sorted[pos]]
            if server in served:
                continue
            served.append(server)
            if self._error_limited[server] > time.time():
                continue
            try:
                sock = self._client_cache[server].pop()
                yield server, sock
            except IndexError:
                try:
                    address = server
                    username = self._username
                    password = self._password
                    if '@' in server:
                        credentials, address = server.split('@', 1)
                        username, password = credentials.split(':', 1)
                    if ':' in address:
                        host, port = address.split(':')
                    else:
                        host = server
                        port = DEFAULT_MEMCACHED_PORT
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    sock.settimeout(self._connect_timeout)
                    sock.connect((host, int(port)))
                    sock.settimeout(self._io_timeout)
                    self._authenticate(host, sock, username, password)
                    yield server, sock
                except Exception as e:
                    self._exception_occurred(server, e, 'connecting')
        raise MemcacheConnectionError('Unable to get server connection')

    def _return_conn(self, server, sock):
        self._client_cache[server].append(sock)

    def make_packet(self, opcode, key='', value='', extras=''):
        return struct.pack(
            MEMCACHE_HEADER, 0x80, opcode, len(key), len(extras), 0x0, 0x0,
            len(extras) + len(key) + len(value), 0, 0) + extras + key + value

    def recvall(self, sock, length):
        data = ''
        while len(data) < length:
            data += sock.recv(length - len(data))
        return data

    def read_packet(self, sock):
        header = self.recvall(sock, MEMCACHE_HEADER_LEN)
        (magic, opcode, key_len, extras_len, data_type, status, body_len,
         opaque, cas) = struct.unpack(MEMCACHE_HEADER, header)
        if status == STATUS_UNAUTHORIZED:
            raise MemcacheConnectionError('Not authenticated')
        body = self.recvall(sock, body_len)
        extras = body[key_len:extras_len]
        value = body[key_len + extras_len:body_len]
        return status, value, extras

    def _authenticate(self, host, sock, username, password):
        if not username or not password:
            logging.info('No credentials for %s, not authenticating', host)
            return
        sock.sendall(self.make_packet(OP_SASL_MECHS))
        status, value, extras = self.read_packet(sock)
        if status == STATUS_UNKNOWN_COMMAND:
            raise MemcacheConnectionError('Auth not enabled on memcached')
        mechs = value.split()
        sasl = SaslAuth(host, mechs, username=username,
                        password=password)
        sock.sendall(self.make_packet(OP_SASL_REQ, sasl.mechanism,
                                      sasl.request()))
        status, challenge, extras = self.read_packet(sock)
        while status == STATUS_CONTINUE_AUTH:
            sock.sendall(self.make_packet(OP_SASL_CONTINUE, sasl.mechanism,
                                          sasl.respond(challenge)))
            status, challenge, extras = self.read_packet(sock)
        if status == STATUS_UNAUTHORIZED:
            raise MemcacheConnectionError('Authentication failed')

    def get(self, key):
        key = md5hash(key)
        packet = self.make_packet(OP_GET, key)
        for (server, sock) in self._get_conns(key):
            try:
                sock.sendall(packet)
                status, value, extras = self.read_packet(sock)
                if status != STATUS_NO_ERROR:
                    return
                self._return_conn(server, sock)
                flags = struct.unpack('!I', extras)[0]
                if flags & JSON_FLAG:
                    return json.loads(value)
                else:
                    return value
            except Exception as e:
                self._exception_occurred(server, e)

    def set(self, key, value, serialize=True, time=0, min_compress_len=0):
        key = md5hash(key)
        if time > (30 * 24 * 60 * 60):
            time += int(time.time())
        extras = struct.pack('!II', JSON_FLAG, time)
        if serialize:
            value = json.dumps(value)
        packet = self.make_packet(OP_SET, key, value, extras)
        for (server, sock) in self._get_conns(key):
            try:
                sock.sendall(packet)
                self.read_packet(sock)
                self._return_conn(server, sock)
                return
            except Exception as e:
                self._exception_occurred(server, e)

    def incr(self, key, delta, time=0):
        key = md5hash(key)
        if time > (30 * 24 * 60 * 60):
            time += int(time.time())
        if delta < 0:
            extras = struct.pack('!QQI', abs(delta), 0, time)
            packet = self.make_packet(OP_DECREMENT, key, '', extras)
        else:
            extras = struct.pack('!QQI', delta, delta, time)
            packet = self.make_packet(OP_INCREMENT, key, '', extras)
        for (server, sock) in self._get_conns(key):
            try:
                sock.sendall(packet)
                status, value, extras = self.read_packet(sock)
                self._return_conn(server, sock)
                if status == STATUS_NO_ERROR:
                    return struct.unpack('!Q', value)[0]
            except Exception as e:
                self._exception_occurred(server, e)

    def decr(self, key, delta, time=0):
        return self.incr(key, -delta, time)

    def delete(self, key):
        key = md5hash(key)
        packet = self.make_packet(OP_DELETE, key)
        for (server, sock) in self._get_conns(key):
            try:
                sock.sendall(packet)
                self.read_packet(sock)
                self._return_conn(server, sock)
                return
            except Exception as e:
                self._exception_occurred(server, e)
