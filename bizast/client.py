import sys
import os
import json
import argparse
import binascii
import getpass as _getpass
from distutils.dir_util import mkpath as mkdirs
import re
import struct
import tempfile

import appdirs
import nacl.signing
import nacl.secret
import nacl.hash
import nacl.utils
from nacl.encoding import RawEncoder as eraw
import requests

import server

cache = appdirs.user_cache_dir('bizast-client', 'zarbosoft')
root = appdirs.user_data_dir('bizast-client', 'zarbosoft')
keydir = os.path.join(root, 'keys')


def getpass(new):
    if new:
        first = _getpass.getpass('new passphrase')
        second = _getpass.getpass('new passphrase (confirm)')
        if first != second:
            raise ValueError('Passphrases don\'t match')
        return first
    else:
        return _getpass.getpass('current passphrase')


def to_nonce(count):
    return bytes('\0') * 20 + struct.pack('>I', count)


def from_nonce(nonce):
    return struct.unpack('>I', nonce[-4:])[0]


def check_name(name):
    if name.lower() == 'default':
        raise ValueError('Key name [default] is not allowed.')
    if re.search('[\\/]', name):
        raise ValueError('Key name must also be a valid filename.')


def open_key(name, ro=True):
    if not name:
        with open(os.path.join(keydir, 'default'), 'r') as default:
            name = default.read()
    if not name:
        raise RuntimeError('No default key configured')
    filedir = keydir
    filename = os.path.join(keydir, name)
    file = open(filename, 'r+' if not ro else 'r')
    if not file:
        filename = name
        filedir, ign = os.path.split(name)
        file = open(name, 'r+' if not ro else 'r')
    if not file:
        raise RuntimeError(
            'Key [{}] is neither a stored key or key path'.format(name))
    return file, filedir, filename


def get_seed(key_data):
    seed = key_data.get('seed')
    counter = 0
    if not seed:
        nonce = binascii.unhexlify(key_data.get('nonce'))
        counter = from_nonce(nonce)
        passphrase = nacl.hash.sha256(getpass(False), encoder=eraw)
        box = nacl.secret.SecretBox(passphrase)
        seed = box.decrypt(
            binascii.unhexlify(key_data.get('encrypted_seed')), 
            nonce=nonce, 
            encoder=eraw)
    else:
        seed = binascii.unhexlify(seed)
    return seed, counter


def write_default(filename):
    open(os.path.join(keydir, 'default'), 'w').write(filename)


def main():
    parser = argparse.ArgumentParser(
        description='Bizast multifunction tool',
    )
    commands = parser.add_subparsers(dest='command')

    def add_common_subparser(*pargs, **kwargs):
        out = commands.add_parser(*pargs, **kwargs)
        out.add_argument(
            '-v',
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )
        return out

    gen_command = add_common_subparser('gen', description='Generate key')
    gen_command.add_argument(
        'name', 
        help='Name of key. Preferably something easy to type',
    )
    gen_command.add_argument(
        '-n', 
        '--nopassphrase',
        help='Don\'t encrypt key',
        action='store_true',
    )
    gen_command.add_argument(
        '-s', 
        '--store',
        help='Store in default location',
        action='store_true',
    )
    gen_command.add_argument(
        '-d', 
        '--default',
        help='Make stored key default (implies store)',
        action='store_true',
    )
    
    mod_command = add_common_subparser('mod', description='Modify key')
    mod_command.add_argument(
        '-k',
        '--key', 
        help='Key name or filename.  Use default key if unspecified',
    )
    mod_command.add_argument(
        '-p', 
        '--passphrase',
        help='Set or change passphrase',
        action='store_true',
    )
    mod_command.add_argument(
        '-r', 
        '--remove-passphrase',
        help='Remove passphrase',
        action='store_true',
    )
    mod_command.add_argument(
        '-n', 
        '--name',
        help='Change key name',
    )
    mod_command.add_argument(
        '-d', 
        '--default',
        help='Make key default',
        action='store_true',
    )
    
    pub_command = add_common_subparser('pub', description='Publish resource')
    pub_command.add_argument(
        '-k',
        '--key', 
        help='Key name or filename',
    )
    pub_command.add_argument(
        'name', 
        help='Name of resource',
    )
    pub_command.add_argument(
        'resource', 
        help='URI of resource to publish',
    )
    pub_command.add_argument(
        '-r', 
        '--version', 
        help='Explicitly set version',
        type=int,
    )
    pub_command.add_argument(
        '-w',
        '--webhost',
        help='Bizast web server host',
        default='localhost',
    )
    pub_command.add_argument(
        '-p',
        '--webport',
        help='Bizast web server port',
        type=int,
        default=server.default_webport,
    )

    args = parser.parse_args()

    mkdirs(keydir)

    if args.command == 'gen':
        check_name(args.name)
        out = {
            'name': args.name,
        }
        seed = nacl.utils.random()
        if args.nopassphrase:
            out['seed'] = seed
        else:
            passphrase = nacl.hash.sha256(getpass(True), encoder=eraw)
            box = nacl.secret.SecretBox(passphrase)
            nonce = to_nonce(0)
            encrypted_seed = box.encrypt(seed, nonce, encoder=eraw)
            out['nonce'] = binascii.hexlify(nonce)
            out['encrypted_seed'] = binascii.hexlify(encrypted_seed.ciphertext)
        
        signing_key = nacl.signing.SigningKey(seed, encoder=eraw)
        raw_signing_key = signing_key.verify_key.encode(eraw)
        out['fingerprint'] = server.gen_fingerprint(raw_signing_key)

        if args.default:
            args.store = True
        if args.store:
            filename = os.path.join(keydir, args.name)
            fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            file = os.fdopen(fd, 'w')
            if not file:
                raise RuntimeError(
                    'Key file [{}] already exists'.format(filename))
            file.write(json.dumps(out))
            if args.default:
                write_default(filename)
        else:
            print(json.dumps(out))

    elif args.command == 'mod':
        file, filedir, filename = open_key(args.key, ro=False)
        if args.name or args.passphrase or args.remove_passphrase:
            old = json.loads(file.read())
            out = {}
            if args.name:
                check_name(args.name)
            out['name'] = args.name or old['name']
            out['fingerprint'] = old['fingerprint']
            if args.passphrase and args.remove_passphrase:
                parser.error('Cannot use -r and -p simultaneously')
            if args.passphrase or args.remove_passphrase:
                seed, counter = get_seed(old)
                if args.passphrase:
                    passphrase = nacl.hash.sha256(getpass(True), encoder=eraw)
                    box = nacl.secret.SecretBox(passphrase)
                    nonce = to_nonce(counter + 1)
                    encrypted_seed = box.encrypt(seed, nonce, encoder=eraw)
                    out['nonce'] = binascii.hexlify(nonce)
                    out['encrypted_seed'] = binascii.hexlify(encrypted_seed.ciphertext)
                elif args.remove_passphrase:
                    out['seed'] = binascii.hexlify(seed)
            else:
                seed = old.get('seed')
                if seed:
                    out['seed'] = seed
                else:
                    out['encrypted_seed'] = old['encrypted_seed']
                    out['nonce'] = old['nonce']
            temp = tempfile.NamedTemporaryFile(dir=filedir, delete=False)
            temp.write(json.dumps(out))
            temp.close()
            os.rename(temp.name, filename)
        if args.default:
            write_default(filename)

    elif args.command == 'pub':
        file, filedir, filename = open_key(args.key)
        signing_seed, ign = get_seed(json.loads(file.read()))
        signing_key = nacl.signing.SigningKey(signing_seed, encoder=eraw)
        raw_signing_key = signing_key.verify_key.encode(eraw)
        key = '{}:{}'.format(
            args.name, 
            server.gen_fingerprint(raw_signing_key))
        resp = requests.get(
            'http://{}:{}/{}'.format(args.webhost, args.webport, key),
            headers={
                'Accept': 'application/json',
            },
        )
        version = 0
        if resp:
            version = resp.json()['version'] + 1
        value = {
            'message': args.resource,
            'version': version,
            'key': binascii.hexlify(raw_signing_key),
            'name': args.name,
        }
        plaintext = server.plaintext(value)
        value['signature'] = binascii.hexlify(
            signing_key.sign(plaintext).signature)
        resp = requests.post(
            'http://{}:{}/'.format(args.webhost, args.webport), 
            data=json.dumps(value),
        )
        if resp:
            print(key)
        else:
            sys.stderr.write('Publish failed to {} [{}]\n'.format(
                resp.url,
                resp.status_code,
            ))

if __name__ == '__main__':
    main()
