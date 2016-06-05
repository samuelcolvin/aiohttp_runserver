import re
import click
import logging

dft_logger = logging.getLogger('aiohttp_runserver.default')
access_logger = logging.getLogger('aiohttp.access')
aux_logger = logging.getLogger('dev_server')

LOG_COLOURS = {
    logging.DEBUG: 'white',
    logging.INFO: 'green',
    logging.WARN: 'yellow',
}


class ClickHandler(logging.Handler):

    def emit(self, record):
        log_entry = self.format(record)
        colour = LOG_COLOURS.get(record.levelno, 'red')
        m = re.match('^(\[.*?\])', log_entry)
        if m:
            time = click.style(m.groups()[0], fg='magenta')
            msg = click.style(log_entry[m.end():], fg=colour)
            click.echo(time + msg)
        else:
            click.secho(log_entry, fg=colour)


class AuxiliaryLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        colour = LOG_COLOURS.get(record.levelno, 'red')
        m = re.match('^(\[.*?\] )', log_entry)
        time = click.style(m.groups()[0], fg='magenta')
        msg = log_entry[m.end():]
        if record.levelno == logging.INFO and msg.startswith(' >'):
            msg = '{} {}'.format(click.style(' >', fg='blue'), msg[3:])
        else:
            msg = click.style(msg, fg=colour)
        click.echo(time + msg)


def setup_logging(verbose=False):
    log_level = logging.DEBUG if verbose else logging.INFO

    for h in dft_logger.handlers:
        if isinstance(h, ClickHandler):
            return
    dft_hdl = ClickHandler()
    fmt = '[%(asctime)s] %(message)s'
    formatter = logging.Formatter(fmt, datefmt='%H:%M:%S')
    dft_hdl.setFormatter(formatter)
    dft_logger.addHandler(dft_hdl)
    dft_logger.setLevel(log_level)
    access_logger.addHandler(dft_hdl)
    access_logger.setLevel(log_level)

    aux_hdl = AuxiliaryLogHandler()
    formatter = logging.Formatter(fmt, datefmt='%H:%M:%S')
    aux_hdl.setFormatter(formatter)
    aux_logger.addHandler(aux_hdl)
    aux_logger.setLevel(log_level)
