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
import naclkeys

cache = appdirs.user_cache_dir('bizast-client', 'zarbosoft')
root = appdirs.user_data_dir('bizast-client', 'zarbosoft')


def main():
    parser = argparse.ArgumentParser(
        description='Bizast publishing tool',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Enable verbose output',
    )
    parser.add_argument(
        '-k',
        '--key', 
        help='Key name or filename',
    )
    parser.add_argument(
        'name', 
        help='Name of resource',
    )
    parser.add_argument(
        'resource', 
        help='URI of resource to publish',
    )
    parser.add_argument(
        '-r', 
        '--version', 
        help='Explicitly set version',
        type=int,
    )
    parser.add_argument(
        '-w',
        '--webhost',
        help='Bizast web server host',
        default='localhost',
    )
    parser.add_argument(
        '-p',
        '--webport',
        help='Bizast web server port',
        type=int,
        default=server.default_webport,
    )

    args = parser.parse_args()

    publisher = naclkeys.Key.open(args.key)
    key = '{}:{}'.format(
        args.name, 
        publisher.fingerprint)

    # Get old record if present
    resp = requests.get(
        'http://{}:{}/{}'.format(args.webhost, args.webport, key),
        headers={
            'Accept': 'application/json',
        },
    )
    version = 0
    if resp:
        version = resp.json()['version'] + 1

    # Put together new record
    value = {
        'message': args.resource,
        'version': version,
        'key': binascii.hexlify(publisher.verify_key()),
        'name': args.name,
    }
    plaintext = server.plaintext(value)
    value['signature'] = binascii.hexlify(publisher.sign(plaintext))

    # Publish
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
