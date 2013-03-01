import hmac
import uuid
from urllib2 import parse_http_list, parse_keqv_list
from hashlib import md5


def digest_md5(challenge, user, password, host):
    chal = parse_keqv_list(parse_http_list(challenge))
    if 'rspauth' in chal:
        return ''
    digest_uri = 'memcached/%s' % chal.get('realm', host)
    ncvalue = '00000001'
    realm = chal.get('realm', '')
    cnonce = str(uuid.uuid4()).replace('-', '')[0:16]
    a1 = '%s:%s:%s' % (user, realm, password)
    if chal.get('algorithm', 'md5').lower() == 'md5':
        ha1 = md5(a1).hexdigest()
    elif chal['algorithm'].lower() == 'md5-sess':
        ha1 = md5('%s:%s:%s' % (md5(a1).digest(), chal['nonce'], cnonce)
                  ).hexdigest()
    ha2 = md5('AUTHENTICATE:%s' % digest_uri).hexdigest()
    if chal.get('qop') in ('auth', 'auth-init'):
        response = md5(':'.join((ha1, chal['nonce'], ncvalue, cnonce,
                       chal['qop'], ha2))).hexdigest()
    else:
        response = md5('%s:%s:%s' % (ha1, chal['nonce'], ha2)).hexdigest()
    resp = {'username': user, 'nonce': chal['nonce'], 'nc': ncvalue,
            'cnonce': cnonce, 'response': response, 'digest-uri': digest_uri}
    if 'qop' in chal:
        resp['qop'] = chal.get('qop')
    if realm:
        resp['realm'] = realm
    return ', '.join('%s="%s"' % item for item in resp.iteritems())


class SaslAuth(object):
    def __init__(self, host, mechs, username, password):
        self.username = username
        self.password = password
        self.host = host
        self.mechanism = None
        for mech in ('LOGIN', 'PLAIN', 'CRAM-MD5', 'DIGEST-MD5'):
            if mech in mechs:
                self.mechanism = mech
        if not self.mechanism:
            raise Exception('Suitable mechanism not found.')

    def request(self):
        if self.mechanism == 'PLAIN':
            return '\x00%s\x00%s' % (self.username, self.password)
        return ''

    def respond(self, challenge):
        if self.mechanism == 'DIGEST-MD5':
            return digest_md5(challenge, self.username, self.password,
                              self.host)
        elif self.mechanism == 'CRAM-MD5':
            h = hmac.new(self.password, challenge)
            return '%s %s' % (self.username, h.hexdigest())
        elif self.mechanism == 'PLAIN':
            return '\x00%s\x00%s' % (self.username, self.password)
        elif self.mechanism == 'LOGIN':
            if 'username' in challenge.lower().replace(' ', ''):
                return self.username
            elif 'password' in challenge.lower():
                return self.password
