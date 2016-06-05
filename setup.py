from setuptools import setup
from aiohttp_runserver import VERSION

description = 'Development server for aiohttp apps.'
long_description = """\
See `github.com/samuelcolvin/aiohttp_runserver <https://github.com/samuelcolvin/aiohttp_runserver>`__ for details.
"""


def check_livereload_js():
    import hashlib
    from pathlib import Path
    live_reload_221_hash = 'a451e4d39b8d7ef62d380d07742b782f'
    live_reload_221_url = 'https://raw.githubusercontent.com/livereload/livereload-js/v2.2.1/dist/livereload.js'

    path = Path(__file__).absolute().parent.joinpath('aiohttp_runserver/livereload.js')

    def check_path():
        with path.open('rb') as fr:
            file_hash = hashlib.md5(fr.read()).hexdigest()
        return file_hash == live_reload_221_hash

    if path.is_file():
        if check_path():
            return

    import urllib.request

    print('downloading livereload:\nurl:  {}\npath: {}'.format(live_reload_221_url, path))
    with urllib.request.urlopen(live_reload_221_url) as r:
        with path.open('wb') as fw:
            fw.write(r.read())

    if not check_path():
        raise RuntimeError('checksums do not match for {} after download'.format(path))

check_livereload_js()


setup(
    name='aiohttp_runserver',
    version=str(VERSION),
    description=description,
    long_description=long_description,
    classifiers=[
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='aiohttp,debug,development,reload,livereload,server',
    author='Samuel Colvin',
    author_email='s@muelcolvin.com',
    url='https://github.com/samuelcolvin/aiohttp-runserver',
    license='MIT',
    packages=['aiohttp_runserver'],
    zip_safe=True,
    package_data={'aiohttp_runserver': ['livereload.js']},
    entry_points="""
        [console_scripts]
        aiohttp-runserver=aiohttp_runserver.main:cli
        arun=aiohttp_runserver.main:cli
    """,
    install_requires=[
        'aiohttp>=0.21.6',
        'click>=6.2',
        'watchdog==0.8.3',
    ]
)
