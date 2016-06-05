import os
from pathlib import Path
from pprint import pformat

import click
from watchdog.observers import Observer

from aiohttp_runserver import VERSION
from .logs import dft_logger, setup_logging, AuxiliaryLogHandler
from .serve import create_auxiliary_app, import_string
from .watch import CodeFileEventHandler, StaticFileEventEventHandler, AllCodeEventEventHandler

static_help = ''
static_url_help = ''
port_help = ''
aux_port_help = ''
verbose_help = 'Enable verbose output.'


def run_apps(app_path, **config):
    _, code_path = import_string(app_path)
    config.update(
        app_path=app_path,
        code_path=str(code_path),
        static_path=str(Path(config.pop('static_path')).resolve()),
    )
    dft_logger.debug('config:\n%s', pformat(config))

    aux_app = create_auxiliary_app(**config)

    observer = Observer()
    code_file_eh = CodeFileEventHandler(aux_app, config)
    dft_logger.debug('starting CodeFileEventHandler to watch %s', config['code_path'])
    observer.schedule(code_file_eh, config['code_path'], recursive=True)

    all_code_file_eh = AllCodeEventEventHandler(aux_app, config)
    observer.schedule(all_code_file_eh, config['code_path'], recursive=True)

    static_path = config['static_path']
    if static_path:
        static_file_eh = StaticFileEventEventHandler(aux_app, config)
        dft_logger.debug('starting StaticFileEventEventHandler to watch %s', static_path)
        observer.schedule(static_file_eh, static_path, recursive=True)
    observer.start()

    loop = aux_app.loop
    handler = aux_app.make_handler(access_log=None)
    srv = loop.run_until_complete(loop.create_server(handler, '0.0.0.0', config['aux_port']))

    url = 'http://localhost:{aux_port}'.format(**config)
    dft_logger.info('Starting aux server at %s %s', url, AuxiliaryLogHandler.prefix)

    static_path = config['static_path']
    if static_path:
        rel_path = Path(static_path).absolute().relative_to(os.getcwd())
        dft_logger.info('serving static files from ./%s at %s%s', rel_path, url, config['static_url'])

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no branch
        pass
    finally:
        dft_logger.debug('shutting down auxiliary server...')
        loop.create_task(aux_app.close_websockets())
        observer.stop()
        observer.join()
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(aux_app.shutdown())
        loop.run_until_complete(handler.finish_connections(2))
        loop.run_until_complete(aux_app.cleanup())
    loop.close()


@click.command()
@click.version_option(VERSION, '-V', '--version')
@click.argument('app', 'app_path', required=True)
@click.option('-s', '--static', 'static_path',
              type=click.Path(exists=True, dir_okay=True, file_okay=False), help=static_help)
@click.option('-su', '--static-url', default='/static/', help=static_url_help)
@click.option('-p', '--port', 'main_port', default=8000, help=port_help)
@click.option('-ap', '--aux-port', default=8001, help=aux_port_help)
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def cli(app, verbose, **config):
    """
    Run development server for aiohttp apps.
    """
    setup_logging(verbose)
    run_apps(app, **config)
