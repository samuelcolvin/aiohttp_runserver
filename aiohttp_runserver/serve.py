import logging
import asyncio
import re
import json
from pathlib import Path

import click
import aiohttp
from aiohttp.web_exceptions import HTTPNotModified, HTTPNotFound
from aiohttp import web
from aiohttp.web_urldispatcher import StaticRoute

from .common import import_string

logger = logging.getLogger('dev_server')


class DevLogHandler(logging.Handler):
    colours = {
        logging.DEBUG: 'white',
        logging.INFO: 'blue',
        logging.WARN: 'yellow',
    }

    def __init__(self, *args):
        super().__init__(*args)
        self._width = click.get_terminal_size()[0]

    def emit(self, record):
        log_entry = self.format(record)
        m = re.match('^(\[.*?\] )', log_entry)
        time = click.style(m.groups()[0], fg='magenta')
        msg = log_entry[m.end():]
        if record.levelno == logging.INFO and msg.startswith(' >'):
            msg = '{} {}'.format(click.style(' >', fg='blue'), msg[3:])
        else:
            msg = click.style(msg, fg=self.colours.get(record.levelno, 'red'))
        click.echo(time + msg)

handler = DevLogHandler()
formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

LIVE_RELOAD_SNIPPET = b'\n<script src="http://localhost:%d/livereload.js"></script>\n'


def modify_main_app(app, **config):
    static_path = config['static_path']
    if static_path:
        serve_root = '{}/'.format(static_path)
        app.router.register_route(CustomStaticRoute('static-router', config['static_url'], serve_root))

    live_reload_snippet = LIVE_RELOAD_SNIPPET % config['aux_port']

    async def on_prepare(request, response):
        if 'text/html' in response.content_type:
            response.body += live_reload_snippet
    app.on_response_prepare.append(on_prepare)


def serve_main_app(**config):
    app_factory, _ = import_string(config['app_path'])

    loop = asyncio.new_event_loop()
    app = app_factory(loop=loop)

    modify_main_app(app, **config)
    handler = app.make_handler(access_log_format='[%t] %r %s %b')
    srv = loop.run_until_complete(loop.create_server(handler, '0.0.0.0', config['main_port']))

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no branch
        pass
    finally:
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(app.shutdown())
        loop.run_until_complete(handler.finish_connections(4))
        loop.run_until_complete(app.cleanup())
    loop.close()


WS = 'websockets'


class AuxiliaryApplication(web.Application):
    def static_reload(self, src_path):
        config = self['config']
        static_root = config['static_path']
        path = Path(src_path).relative_to(static_root)
        cli_count = len(self[WS])
        if cli_count == 0:
            return
        logger.info('prompting reload of %s on %d client%s', path, cli_count, '' if cli_count == 1 else 's')
        for i, ws in enumerate(self[WS]):
            data = {
                'command': 'reload',
                'path': str(path),  # TODO subdirectory?
                'liveCSS': True,
                'liveImg': True,
            }
            ws.send_str(json.dumps(data))


def create_auxiliary_app(*, loop=None, **config):
    loop = loop or asyncio.new_event_loop()
    app = AuxiliaryApplication(loop=loop)
    app[WS] = []
    app['config'] = config

    app.router.add_route('GET', '/livereload.js', lr_script_handler)
    app.router.add_route('GET', '/livereload', websocket_handler)
    return app


async def lr_script_handler(request):
    script_key = 'livereload_script'
    lr_script = request.app.get(script_key)
    if lr_script is None:
        lr_path = Path(__file__).absolute().parent.joinpath('livereload.js')
        with lr_path.open('rb') as f:
            lr_script = f.read()
            request.app[script_key] = lr_script
    return web.Response(body=lr_script, content_type='application/javascript')


async def websocket_handler(request):

    ws = web.WebSocketResponse()
    request.app[WS].append(ws)
    await ws.prepare(request)
    ws_type_lookup = {k.value: v for v, k in aiohttp.MsgType.__members__.items()}

    async for msg in ws:
        if msg.tp == aiohttp.MsgType.text:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError as e:
                logger.error('JSON decode error: %s', str(e))
            else:
                command = data['command']
                if command == 'hello':
                    if 'http://livereload.com/protocols/official-7' not in data['protocols']:
                        logger.error('live reload protocol 7 not supported by client %s', msg.data)
                        ws.close()
                    else:
                        handshake = {
                            'command': 'hello',
                            'protocols': [
                                'http://livereload.com/protocols/official-7',
                            ],
                            'serverName': 'livereload-aiohttp',
                        }
                        ws.send_str(json.dumps(handshake))
                elif command == 'info':
                    logger.debug('browser connected at %s', data['url'])
                    logger.debug('browser plugins: %s', data['plugins'])
                else:
                    logger.error('Unknown ws message %s', msg.data)
        elif msg.tp == aiohttp.MsgType.error:
            logger.error('ws connection closed with exception %s',  ws.exception())
        else:
            logger.error('unknown websocket message type %s, data: %s', ws_type_lookup[msg.tp], msg.data)

    # TODO gracefully close websocket connections on app shutdown
    logger.debug('browser disconnected')
    request.app[WS].remove(ws)

    return ws


class CustomStaticRoute(StaticRoute):
    def __init__(self, *args, **kwargs):
        self._asset_path = None  # TODO
        super().__init__(*args, **kwargs)

    async def handle(self, request):
        filename = request.match_info['filename']
        try:
            filepath = self._directory.joinpath(filename).resolve()
        except (ValueError, FileNotFoundError, OSError):
            pass
        else:
            if filepath.is_dir():
                request.match_info['filename'] = str(filepath.joinpath('index.html').relative_to(self._directory))
        status, length = 'unknown', ''
        try:
            response = await super().handle(request)
        except HTTPNotModified:
            status, length = 304, 0
            raise
        except HTTPNotFound:
            _404_msg = '404: Not Found\n\n' + _get_asset_content(self._asset_path)
            response = web.Response(body=_404_msg.encode('utf8'), status=404)
            status, length = response.status, response.content_length
        else:
            status, length = response.status, response.content_length
        finally:
            l = logger.info if status in {200, 304} else logger.warning
            l(' > %s %s %s %s', request.method, request.path, status, _fmt_size(length))
        return response


def _get_asset_content(asset_path):
    if not asset_path:
        return ''
    with asset_path.open() as f:
        return 'Asset file contents:\n\n{}'.format(f.read())


def _fmt_size(num):
    if num == '':
        return ''
    if num < 1024:
        return '{:0.0f}B'.format(num)
    else:
        return '{:0.1f}KB'.format(num / 1024)
