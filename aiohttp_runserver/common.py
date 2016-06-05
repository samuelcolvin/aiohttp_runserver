import os
import sys
import logging
from pathlib import Path
from importlib import import_module, reload

logger = logging.getLogger('arun')


def import_string(hybrid_path, _trying_again=False):
    """
    Import attribute/class from from a python module. Raise ImportError if the import failed.

    Approximately stolen from django.

    :param hybrid_path: "path" to file & attribute in the form path/to/file.py:attribute
    :return: (attribute, Path object for directory of file)
    """
    try:
        file_path, class_name = hybrid_path.rsplit(':', 1)
    except ValueError as e:
        raise ImportError("%s doesn't look like a proper path" % hybrid_path) from e

    module_path = file_path.replace('.py', '').replace('/', '.')

    try:
        module = import_module(module_path)
    except ImportError:
        if _trying_again:
            raise
        # add current working directory to pythonpath and try again
        p = os.getcwd()
        logger.debug('adding current working director %s to pythonpath and reattempting import', p)
        sys.path.append(p)
        return import_string(hybrid_path, True)

    reload(module)

    try:
        attr = getattr(module, class_name)
    except AttributeError as e:
        raise ImportError('Module "%s" does not define a "%s" attribute/class' % (module_path, class_name)) from e

    directory = Path(module.__file__).parent
    return attr, directory
