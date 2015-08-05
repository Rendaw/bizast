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

root = appdirs.user_data_dir('naclkeys', 'zarbosoft')
keydir = os.path.join(root, 'keys')


# TODO file leaks

class Key:
    def __init__(self, **kwargs):
        self.new = kwargs.pop('new')
        self.name = kwargs.pop('name')
        self.filename = kwargs.pop('filename', None)
        self.fileroot = kwargs.pop('fileroot', None)
        self.passphrase = kwargs.pop('passphrase', None)
        self.fingerprint = kwargs.pop('fingerprint')
        self.seed = kwargs.pop('seed', None)
        self.counter = kwargs.pop('counter', None)
        self.encrypted_seed = kwargs.pop('encrypted_seed', None)
        if not self.seed and not self.encrypted_seed:
            raise ValueError('Invalid key: missing both seed and encrypted_seed')
        if self.encrypted_seed and self.counter is None:
            raise ValueError('Invalid key: missing counter/nonce for encrypted_seed')

    @classmethod
    def new(cls, name):
        Key._check_name(name)
        seed = nacl.utils.random()
        signing_key = nacl.signing.SigningKey(seed, encoder=eraw)
        verify_key = signing_key.verify_key.encode(eraw)
        return cls(
            new=True,
            name=name,
            fingerprint=binascii.hexlify(nacl.hash.sha256(verify_key, encoder=eraw)),
            seed=seed,
        )
        return self

    @classmethod
    def open(cls, name=None, passphrase=None):
        if not name:
            with open(os.path.join(keydir, 'default'), 'r') as default:
                name = default.read()
        if not name:
            raise RuntimeError('No default key configured')
        fileroot = keydir
        filename = os.path.join(fileroot, name)
        file = open(filename, 'r')
        if not file:
            filename = name
            fileroot, ign = os.path.split(name)
            file = open(name, 'r')
        if not file:
            raise RuntimeError(
                'Key [{}] is neither a stored key or key path'.format(name))
        data = json.loads(file.read())
        counter = None
        seed = None
        encrypted_seed = None
        if 'nonce' in data:
            counter = Key._from_nonce(binascii.unhexlify(data['nonce']))
        if 'seed' in data:
            seed = binascii.unhexlify(data['seed'])
        if 'encrypted_seed' in data:
            encrypted_seed = binascii.unhexlify(data['encrypted_seed'])
        fingerprint = data['fingerprint']
        file.close()
        return cls(
            new=False,
            name=name,
            filename=filename,
            fileroot=fileroot,
            passphrase=passphrase,
            fingerprint=fingerprint,
            seed=seed,
            counter=counter,
            encrypted_seed=encrypted_seed,
        )

    def dump(self):
        out = {
            'fingerprint': self.fingerprint,
            'name': self.name,
        }
        if self.counter is not None:
            out['nonce'] = binascii.hexlify(self._to_nonce(self.counter))
        if self.encrypted_seed:
            out['encrypted_seed'] = binascii.hexlify(self.encrypted_seed)
        else:
            out['seed'] = binascii.hexlify(self.seed)
        return json.dumps(out)

    def save(self, default=False):
        if not self.fileroot:
            self.fileroot = keydir
            mkdirs(keydir)
        if not self.filename:
            self.filename = os.path.join(self.fileroot, self.name)
        if self.new:
            fd = os.open(self.filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            file = os.fdopen(fd, 'w')
            if not file:
                raise RuntimeError(
                    'Key file [{}] already exists'.format(filename))
            file.write(self.dump())
            file.close()
            self.new = False
        else:
            temp = tempfile.NamedTemporaryFile(dir=self.fileroot, delete=False)
            temp.write(self.dump())
            temp.close()
            os.rename(temp.name, self.filename)
        if default:
            self._write_default(self.filename)

    def verify_key(self):
        self._get_seed()
        signing_key = nacl.signing.SigningKey(self.seed, encoder=eraw)
        return signing_key.verify_key.encode(eraw)

    def sign(self, message):
        self._get_seed()
        signing_key = nacl.signing.SigningKey(self.seed, encoder=eraw)
        return signing_key.sign(message).signature

    def set_passphrase(self, passphrase=None):
        self._get_seed()
        if not passphrase:
            passphrase = self._getpass(True)
        passphrase_seed = nacl.hash.sha256(passphrase, encoder=eraw)
        box = nacl.secret.SecretBox(passphrase_seed)
        if self.counter is None:
            self.counter = 0
        else:
            self.counter += 1
        nonce = self._to_nonce(self.counter)
        self.encrypted_seed = box.encrypt(self.seed, nonce, encoder=eraw).ciphertext
        self.passphrase = passphrase

    def remove_passphrase(self):
        self._get_seed()
        self.encrypted_seed = None

    def _get_seed(self):
        if not self.seed:
            if not self.passphrase:
                self.passphrase = self._getpass(False)
            passphrase_seed = nacl.hash.sha256(self.passphrase, encoder=eraw)
            box = nacl.secret.SecretBox(passphrase_seed)
            nonce = self._to_nonce(self.counter)
            self.seed = box.decrypt(self.encrypted_seed, nonce=nonce, encoder=eraw)

    @staticmethod
    def _getpass(new):
        if new:
            first = _getpass.getpass('new passphrase')
            second = _getpass.getpass('new passphrase (confirm)')
            if first != second:
                raise ValueError('Passphrases don\'t match')
            return first
        else:
            return _getpass.getpass('current passphrase')

    @staticmethod
    def _to_nonce(count):
        return bytes('\0') * 20 + struct.pack('>I', count)

    @staticmethod
    def _from_nonce(nonce):
        return struct.unpack('>I', nonce[-4:])[0]

    @staticmethod
    def _check_name(name):
        if name.lower() == 'default':
            raise ValueError('Key name [default] is not allowed.')
        if re.search('[\\/]', name):
            raise ValueError('Key name must also be a valid filename.')

    @staticmethod
    def _write_default(filename):
        open(os.path.join(keydir, 'default'), 'w').write(filename)


def main():
    parser = argparse.ArgumentParser(
        description='NaCl key management tool',
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
        '-u', 
        '--dump',
        help='Print rather than store key',
        action='store_true',
    )
    gen_command.add_argument(
        '-a', 
        '--alternate',
        help='Don\'t make the new key the default',
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
        '-d', 
        '--default',
        help='Make key default',
        action='store_true',
    )
    
    args = parser.parse_args()

    mkdirs(keydir)

    if args.command == 'gen':
        key = Key.new(args.name)
        if args.alternate and args.dump:
            parser.error('Can\'t specify both alternate and print')
        if not args.nopassphrase:
            key.set_passphrase()
        if args.dump:
            print(key.dump())
        else:
            key.save(not args.alternate)
            print(key.fingerprint)

    elif args.command == 'mod':
        key = Key.open(args.key, args.passphrase)
        if args.passphrase or args.remove_passphrase:
            if args.passphrase:
                key.set_passphrase()
            elif args.remove_passphrase:
                key.remove_passphrase()
        key.save(args.default)

if __name__ == '__main__':
    main()
