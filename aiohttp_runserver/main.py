from pathlib import Path
from pprint import pformat

import click
from watchdog.observers import Observer

from aiohttp_runserver import VERSION
from .logs import dft_logger, setup_logging
from .serve import create_auxiliary_app, import_string
from .watch import CodeFileEventHandler, StaticFileEventEventHandler


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
    code_file_eh = CodeFileEventHandler(aux_app, config=config)
    dft_logger.debug('starting CodeFileEventHandler to watch %s', config['code_path'])
    observer.schedule(code_file_eh, config['code_path'], recursive=True)

    static_path = config['static_path']
    if static_path:
        static_file_eh = StaticFileEventEventHandler(aux_app, config=config)
        dft_logger.debug('starting StaticFileEventEventHandler to watch %s', static_path)
        observer.schedule(static_file_eh, static_path, recursive=True)
    observer.start()

    dft_logger.debug('Started auxiliary server at http://localhost:%s', config['aux_port'])

    loop = aux_app.loop
    handler = aux_app.make_handler(access_log_format='%t %r %s %b')
    srv = loop.run_until_complete(loop.create_server(handler, '0.0.0.0', config['aux_port']))

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no branch
        pass
    finally:
        dft_logger.info('shutting down auxiliary server...')
        observer.stop()
        observer.join()
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(aux_app.shutdown())
        loop.run_until_complete(handler.finish_connections(1))
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
