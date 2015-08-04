from setuptools import setup

setup(
    name = 'bizast',
    version = '0.0.1',
    author = 'Rendaw',
    author_email = 'spoo@zarbosoft.com',
    url = 'https://github.com/Rendaw/bizast',
    download_url = 'https://github.com/Rendaw/bizast/tarball/v0.0.1',
    license = 'BSD',
    description = 'A simple distributed domain name system.',
    long_description = open('readme.md', 'r').read(),
    classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: BSD License',
    ],
    install_requires = [
        'PyNaCl',
        'kademlia',
        'appdirs',
        'requests',
    ],
    packages = [
        'bizast', 
    ],
    entry_points = {
        'console_scripts': [
            'bizast_server = bizast.server:main',
            'bizast_client = bizast.client:main',
        ],
    },
    include_package_resources=True,
    package_data={
        '': ['*.html'],
    },
)
