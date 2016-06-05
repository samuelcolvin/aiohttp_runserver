import re
import logging

import click

from aiohttp import web
from watchdog.observers import Observer

from aiohttp_runserver import VERSION
from .common import logger, import_string
from .serve import create_auxiliary_app
from .watch import CodeFileEventHandler, StaticFileEventEventHandler


static_help = ''
static_url_help = ''
port_help = ''
aux_port_help = ''
verbose_help = 'Enable verbose output.'


class ClickHandler(logging.Handler):
    colours = {
        logging.DEBUG: 'white',
        logging.INFO: 'green',
        logging.WARN: 'yellow',
    }

    def emit(self, record):
        log_entry = self.format(record)
        colour = self.colours.get(record.levelno, 'red')
        m = re.match('^(\[.*?\])', log_entry)
        if m:
            time = click.style(m.groups()[0], fg='magenta')
            msg = click.style(log_entry[m.end():], fg=colour)
            click.echo(time + msg)
        else:
            click.secho(log_entry, fg=colour)


def setup_logging(verbose=False):
    for h in logger.handlers:
        if isinstance(h, ClickHandler):
            return
    handler = ClickHandler()
    fmt = '[%(asctime)s] %(message)s'
    formatter = logging.Formatter(fmt, datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


def run_apps(**config):
    aux_app = create_auxiliary_app(**config)

    observer = Observer()
    code_file_eh = CodeFileEventHandler(aux_app, config=config)
    logger.debug('starting CodeFileEventHandler to watch %s', config['code_path'])
    observer.schedule(code_file_eh, config['code_path'], recursive=True)

    static_path = config['static_path']
    if static_path:
        static_file_eh = StaticFileEventEventHandler(aux_app, config=config)
        logger.debug('starting StaticFileEventEventHandler to watch %s', static_path)
        observer.schedule(static_file_eh, static_path, recursive=True)
    observer.start()

    logger.debug('Started auxiliary server at http://localhost:%s', config['aux_port'])

    try:
        web.run_app(aux_app, port=config['aux_port'], print=lambda msg: None)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


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
    _, code_path = import_string(app)
    config.update(
        app_path=app,
        code_path=str(code_path),
    )

    setup_logging(verbose)

    run_apps(**config)
