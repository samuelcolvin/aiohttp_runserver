aiohttp-runserver
=================

CLI based development server for [aiohttp](http://aiohttp.readthedocs.io/en/stable/) based web apps. 

Includes:
* auto-reload on code changes.
* optional static file serving without modifying your app.
* optional Livereload of css, javascript and full pages using [livereload.js](https://github.com/livereload/livereload-js) 
and a livereload websocket interface built using aiohttp's excellent websocket support.
* (soon) optional batteries included support for [aiohttp_debugtoolbar](https://github.com/aio-libs/aiohttp_debugtoolbar).

![aiohttp-runserver-screenshot](https://s3.amazonaws.com/samuelcolvin/aiohttp-runserver-screenshot.png "aiohttp runserver screenshot")

## Usage

Usage is via a command line interface `aiohttp-runserver` or briefer alias `arun`:

    arun --help

Simple usage:

    arun src/app.py get_app

Where `get_app` is a function in `src/app.py` with takes one argument `loop` and returns an instance
of `web.Application`.

## Installation

    pip install aiohttp_runserver

<!-- end description -->

## TODO

* tests (waiting for aiohttp test utils to be released)
* config file support
* integration with https://github.com/aio-libs/aiohttp_debugtoolbar
