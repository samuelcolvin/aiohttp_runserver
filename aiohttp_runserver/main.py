import os
from pathlib import Path
from pprint import pformat

import click
from watchdog.observers import Observer

from aiohttp_runserver import VERSION
from .logs import dft_logger, setup_logging, AuxiliaryLogHandler
from .serve import create_auxiliary_app, import_string
from .watch import CodeFileEventHandler, StaticFileEventEventHandler, AllCodeEventEventHandler


def run_apps(**config):
    _, code_path = import_string(config['app_path'], config['app_factory'])
    static_path = config.pop('static_path')
    config.update(
        code_path=str(code_path),
        static_path=static_path and str(Path(static_path).resolve()),
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
        dft_logger.info('serving static files from ./%s/ at %s%s', rel_path, url, config['static_url'])

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

static_help = "Path of static files to serve, if exclude static files aren't served."
static_url_help = 'URL path to serve static files from, default "/static/".'
livereload_help = 'Whether to inject livereload.js into html page footers to autoreload on changes.'
port_help = 'Port to serve app from, default 8000.'
aux_port_help = 'Port to serve auxiliary app (reload and static) on, default 8001.'
verbose_help = 'Enable verbose output.'

static_path_type = click.Path(exists=True, dir_okay=True, file_okay=False)


@click.command()
@click.version_option(VERSION, '-V', '--version', prog_name='aiohttp-runserver')
@click.argument('app-path', type=click.Path(exists=True, dir_okay=False, file_okay=True), required=True)
@click.argument('app-factory', required=False)
@click.option('-s', '--static', 'static_path', type=static_path_type, help=static_help)
@click.option('--static-url', default='/static/', help=static_url_help)
@click.option('--livereload/--no-livereload', default=True, help=livereload_help)
@click.option('-p', '--port', 'main_port', default=8000, help=port_help)
@click.option('--aux-port', default=8001, help=aux_port_help)
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def cli(verbose, **config):
    """
    Development server for aiohttp apps.
    """
    setup_logging(verbose)
    run_apps(**config)
