import sys
import os
import os.path
import json
import argparse
import binascii
import pkg_resources
import re
import urllib
from distutils.dir_util import mkpath as mkdirs
from collections import OrderedDict
import time

from twisted.application import internet
from twisted.python import log
from twisted.web import resource, server
from twisted.web.resource import NoResource
from twisted.internet import reactor, defer
from twisted.internet.task import react, LoopingCall
from kademlia.network import Server
from kademlia import log
import kademlia.storage
import kademlia.utils
import appdirs
import nacl.signing
import nacl.hash
from nacl.encoding import RawEncoder as eraw
from zope.interface import implements
from pqdict import PQDict

default_webport = 62341
urlmatch = re.compile('[a-zA-Z+]+://')
webprotocol = 'bz://'


def res(path):
    return pkg_resources.resource_filename('bizast', path)


def gen_fingerprint(pubkey):
    return binascii.hexlify(nacl.hash.sha256(pubkey, encoder=eraw))


def plaintext(value):
    return json.dumps({
        'name': value['name'],
        'message': value['message'],
        'version': value['version'],
    }, sort_keys=True)


def split_name_fingerprint(key):
    parts = key.split(':')
    if len(parts) != 2:
        raise ValueError('Key has incorrect number of :\'s: {}'.format(key))
    return parts


def log_info(message):
    print(message)


@defer.inlineCallbacks
def twisted_main(args):
    def validate(hashed_rec_key, value, oldvalue):
        try:
            value = json.loads(value)
            if 'key' not in value:
                raise ValueError('Missing field [key]')
        except Exception as e:
            if args.verbose:
                log_info('Failed validation, record undecipherable: {}'.format(value))
        try:
            key = binascii.unhexlify(value['key'])
            if 'signature' not in value:
                raise ValueError('Missing field [signature]')
            if 'version' not in value:
                raise ValueError('Missing field [version]')
            if 'message' not in value:
                raise ValueError('Missing field [message]')
            if 'name' not in value:
                raise ValueError('Missing field [name]')
            name = value['name']
            if len(name) > 64:
                raise ValueError('Resource name too long (>64 bytes)')
            if len(value['message']) > 512:
                raise ValueError('Message too long (>512 bytes)')
            key = binascii.unhexlify(value['key'])
            fingerprint = gen_fingerprint(key)
            rec_key = '{}:{}'.format(name, fingerprint)
            if hashed_rec_key is not None:
                confirm_hashed_rec_key = kademlia.utils.digest(rec_key)
                if confirm_hashed_rec_key != hashed_rec_key:
                    raise ValueError(
                        'Hashed record keys don\'t match '
                        '(got [{}], expected [{}])'.format(
                            binascii.hexlify(hashed_rec_key),
                            binascii.hexlify(confirm_hashed_rec_key),
                        )
                    )
            signature = binascii.unhexlify(value['signature'])
            nacl.signing.VerifyKey(key, encoder=eraw).verify(
                plaintext(value), signature, encoder=eraw)
            if oldvalue:
                oldvalue = json.loads(oldvalue)
                if oldvalue['version'] >= value['version']:
                    raise ValueError(
                        'Version is too old (existing [{}], new [{}])'.format(
                            oldvalue['version'],
                            value['version'],
                        )
                    )
            return True, rec_key, fingerprint
        except Exception as e:
            if args.verbose:
                log_info('Failed validation: {}, value {}'.format(e, value))
            return False, None, None

    log_observer = log.FileLogObserver(sys.stdout, log.INFO)
    log_observer.start()

    # Load state
    root = appdirs.user_cache_dir(args.instancename, 'zarbosoft')
    mkdirs(root)
    state = {}
    try:
        with open(os.path.join(root, 'state.json'), 'r') as prestate:
            state = json.loads(prestate.read())
    except Exception as e:
        if args.verbose:
            log_info('Failed to load state: {}'.format(e))
    republish = state.get('republish', {})

    # Set up kademlia
    class Storage:
        implements(kademlia.storage.IStorage)

        max_len = 5000

        def __init__(self, ttl=604800):
            # linked
            self.popularity_queue = PQDict()
            self.age_dict = OrderedDict()

            # separate
            self.future_popularity_queue = PQDict()

            self.step = ttl

        def cull(self):
            if len(self.popularity_queue) > self.max_len:
                key = self.popularity_queue.pop()
                del self.age_dict[key]
                del self.dict[key]
            if len(self.future_popularity_queue) > self.max_len:
                self.future_popularity_queue.pop()

        def inc_popularity(self, key):
            current = self.popularity_queue.get(key)
            if current:
                self.popularity_queue[key] = current + self.step
            else:
                current = self.future_popularity_queue.get(key, time.time())
                self.future_popularity_queue[key] = current + self.step

        def _tripleIterable(self):
            ikeys = self.age_dict.iterkeys()
            ibirthday = imap(operator.itemgetter(0), self.age_dict.itervalues())
            ivalues = imap(operator.itemgetter(1), self.age_dict.itervalues())
            return izip(ikeys, ibirthday, ivalues)

        # interface methods below
        def __setitem__(self, key, value):
            age, oldvalue = self.age_dict.get(key) or time.time(), None
            if not validate(key, value, oldvalue)[0]:
                return
            if oldvalue:
                self.age_dict[key] = (age, value)
            else:
                self.age_dict[key] = (time.time(), value)
                self.popularity_queue[key] = time.time()
            self.cull()

        def __getitem__(self, key):
            self.inc_popularity(key)
            self.cull()
            return self.age_dict[key]

        def get(self, key, default=None):
            self.inc_popularity(key)
            self.cull()
            if key in self.age_dict:
                return self.age_dict[key]
            return default

        def iteritemsOlderThan(self, secondsOld):
            minBirthday = time.time() - secondsOld
            zipped = self._tripleIterable()
            matches = takewhile(lambda r: minBirthday >= r[1], zipped)
            return imap(operator.itemgetter(0, 2), matches)

        def iteritems(self):
            self.cull()
            return self.age_dict.iteritems()

    kserver = Server(
        ksize=state.get('ksize', 20), 
        alpha=state.get('alpha', 3), 
        id=(
            binascii.unhexlify(state['id'][0]),
            binascii.unhexlify(state['id'][1]),
        ) if 'id' in state else None, 
        storage=Storage())
    bootstraps = map(tuple, state.get('bootstrap', []))
    for bootstrap in args.bootstrap:
        bhost, bport = bootstrap.split(':', 2)
        bport = int(bport)
        bhost_ip = yield reactor.resolve(bhost)
        bootstraps.append((bhost_ip, bport))
    if args.verbose:
        log_info('Bootstrapping hosts: {}'.format(bootstraps))
    kserver.bootstrap(bootstraps)

    udpserver = internet.UDPServer(args.dhtport, kserver.protocol)
    udpserver.startService()

    # Set up state saver
    def save_state():
        if args.verbose:
            log_info('Saving state')
        state['ksize'] = kserver.ksize
        state['alpha'] = kserver.alpha
        state['id'] = (
            binascii.hexlify(kserver.node.id[0]),
            binascii.hexlify(kserver.node.id[1]),
        )
        state['republish'] = republish
        state['bootstrap'] = kserver.bootstrappableNeighbors()
        with open(os.path.join(root, 'state.json.1'), 'w') as prestate:
            prestate.write(json.dumps(state))
        os.rename(
            os.path.join(root, 'state.json.1'), 
            os.path.join(root, 'state.json'))

    save_state_loop = LoopingCall(save_state)
    save_state_loop.start(60)

    # Set up value republisher
    @defer.inlineCallbacks
    def republish_call():
        for key, val in republish.items():
            if args.verbose:
                log_info('Republishing {}'.format(key))
            yield kserver.set(key, val)
    republish_loop = LoopingCall(republish_call)
    republish_loop.start(1 * 60 * 60 * 24)

    # Set up webserver
    with open(res('redirect_template.html'), 'r') as template:
        redirect_template = template.read()
    class Resource(resource.Resource):
        def getChild(self, child, request):
            return self

        def render_GET(self, request):
            key = urllib.unquote(request.path[1:])
            if key == 'setup':
                with open(res('browser_setup.html'), 'r') as static:
                    return static.read()
            if key.startswith(webprotocol):
                key = key[len(webprotocol):]
            if key.count(':') != 1:
                raise ValueError('Invalid resource id')
            def respond(value):
                if not value:
                    request.write(NoResource().render(request))
                else:
                    valid, ign, ign = validate(None, value, None)
                    if not valid:
                        request.write(NoResource('Received invalid resource: {}'.format(value)).render(request))
                    else:
                        value = json.loads(value)
                        message = value['message']
                        print(request.requestHeaders.getRawHeaders('Accept', []))
                        print('text/html' in request.requestHeaders.getRawHeaders('Accept', []))
                        print(any('text/html' in val for val in request.requestHeaders.getRawHeaders('Accept', [])))
                        if any('text/html' in val for val in request.requestHeaders.getRawHeaders('Accept', [])):
                            if urlmatch.match(message) and '\'' not in message and '"' not in message:
                                request.write(redirect_template.format(
                                    resource=message).encode('utf-8'))
                            else:
                                request.write(message.encode('utf-8'))
                        else:
                            request.write(json.dumps(value))
                request.finish()
            log.msg('GET: key [{}]'.format(key))
            d = kserver.get(key)
            d.addCallback(respond)
            return server.NOT_DONE_YET

        def render_POST(self, request):
            value = request.content.getvalue()
            valid, rec_key, fingerprint = validate(None, value, None)
            if not valid:
                raise ValueError('Failed verification')
            if fingerprint not in args.publish:
                raise ValueError(
                    'Fingerprint {} not in publish whitelist'.format(
                        fingerprint))
            log.msg('SET: key [{}] = val [{}]'.format(rec_key, value))
            republish[rec_key] = value
            def respond(result):
                request.write('Success')
                request.finish()
            d = kserver.set(rec_key, value)
            d.addCallback(respond)
            return server.NOT_DONE_YET
        
        def render_DELETE(self, request):
            key = urllib.unquote(request.path[1:])
            if key.startswith(webprotocol):
                key = key[len(webprotocol):]
            if key.count(':') != 1:
                raise ValueError('Invalid resource id')
            if key not in republish:
                raise ValueError('Not republishing key {}'.format(key))
            del republish[key]
            return 'Success'

    webserver = internet.TCPServer(args.webport, server.Site(Resource()))
    webserver.startService()

def main():
    parser = argparse.ArgumentParser(
        description='Become bizast',
    )
    parser.add_argument(
        '-p',
        '--publish', 
        nargs='+',
        help='Fingerprints of records to actively publish.', 
        default=[],
    )
    parser.add_argument(
        '-d',
        '--dhtport',
        help='DHT port',
        type=int,
        default=26282,
    )
    parser.add_argument(
        '-w',
        '--webport',
        help='Web interface port',
        type=int,
        default=default_webport,
    )
    parser.add_argument(
        '-b',
        '--bootstrap',
        nargs='+',
        help='Bootstrap DHT with host:port',
        default=['soyvindication.dyndns.org:26282'],
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Enable verbose output.',
    )
    parser.add_argument(
        '--instancename',
        help='Instance name (for testing locally with multiple instances)',
        default='bizast',
    )
    args = parser.parse_args()

    reactor.callWhenRunning(twisted_main, args)
    reactor.run()

if __name__ == '__main__':
    main()
