import sys

import yaml
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from devassistant import argument
from devassistant import exceptions
from devassistant import lang
from devassistant import settings
from devassistant.logger import logger
from devassistant import dapi
from devassistant.dapi import dapicli
import logging

actions = {}


def register_action(action):
    """Decorator that adds an action class to active actions.
    Only toplevel actions should be registered, subactions will be
    read from Action.get_subactions()."""
    actions[action] = _register_actions_recursive(action, {})
    return action


def _register_actions_recursive(action, subact_dict):
    for a in action.get_subactions():
        subact_dict[a] = {}
        _register_actions_recursive(a, subact_dict[a])
    return subact_dict


def is_action_run(**kwargs):
    first_act = kwargs.get(settings.SUBASSISTANT_N_STRING.format(0), None)
    if first_act in map(lambda a: a.name, actions.keys()):
        return True
    return False


def get_action_to_run(level=0, **kwargs):
    return _get_action_to_run_recursive(level, actions, **kwargs)


def _get_action_to_run_recursive(level, subact_dict, **kwargs):
    alevel = settings.SUBASSISTANT_N_STRING.format(level)
    aname = kwargs.get(alevel, None)
    if not aname:
        return None
    for a, suba in subact_dict.items():
        if a.name == aname:
            if settings.SUBASSISTANT_N_STRING.format(level + 1) in kwargs:
                return _get_action_to_run_recursive(level + 1, suba, **kwargs)
            else:
                return a


class Action(object):
    """Superclass of custom actions of devassistant"""

    name = 'action'
    description = 'Action description'
    args = []
    hidden = False

    @classmethod
    def get_subactions(cls):
        return []

    @classmethod
    def run(cls, **kwargs):
        """Runs this actions, accepts arguments parsed from cli/retrieved from gui.

        Raises:
            devassistant.exceptions.ExecutionExceptions if something goes wrong
        """
        raise NotImplementedError()


@register_action
class EvalAction(Action):
    name = 'eval'
    description = 'Evaluate input containing Yaml code and context. Internal use only.'
    args = [argument.Argument('input', 'input')]
    hidden = True

    @classmethod
    def run(cls, **kwargs):
        to_run = cls.gather_input(kwargs['input'])
        parsed = yaml.load(to_run, Loader=Loader)
        lang.run_section(parsed.get('run', []), parsed.get('ctxt', {}))

    @classmethod
    def gather_input(cls, recieved):
        if recieved == '-':
            # read from stdin
            to_run = []
            for l in sys.stdin.readlines():
                to_run.append(l)
            to_run = ''.join(to_run)
        else:
            to_run = recieved
        return to_run


@register_action
class HelpAction(Action):
    """Can gather info about all actions and assistant types and print it nicely."""
    name = 'help'
    description = 'Print detailed help'

    @classmethod
    def run(cls, **kwargs):
        """Prints nice help."""
        print(cls.get_help(format_type=kwargs.get('format_type')))

    @classmethod
    def get_help(cls, format_type='ascii'):
        """Constructs and formats help for printing.

        Args:
            format_type: type of formatting for nice output, see format_text for possible values
        """
        top_visible_actions = list(filter(lambda a: not a.hidden, actions))
        # we will justify the action names (and assistant types) to the same width
        just = max(
            max(*map(lambda x: len(x), settings.ASSISTANT_ROLES)),
            max(*map(lambda x: len(x.name), top_visible_actions))
        ) + 2
        text = ['You can either run assistants with:']
        text.append(cls.format_text('da [--debug] {create,modify,prepare,task} ' +\
                                    '[ASSISTANT [ARGUMENTS]] ...',
                                    'bold',
                                    format_type))
        text.append('')
        text.append('Where:')
        text.append(cls.format_action_line('create',
                                           'used for creating new projects',
                                           just,
                                           format_type))
        text.append(cls.format_action_line('modify',
                                           'used for working with existing projects',
                                           just,
                                           format_type))
        text.append(cls.format_action_line('prepare',
                                           'used for preparing environment for upstream projects',
                                            just,
                                            format_type))
        text.append(cls.format_action_line('task',
                                           'used for performing custom tasks not related to a '
                                           'specific project',
                                            just,
                                            format_type))
        text.append('You can shorten "create" to "crt", "modify" to "mod" and "prepare" to "prep".')
        text.append('')
        text.append('Or you can run a custom action:')
        text.append(cls.format_text('da [--debug] [ACTION] [ARGUMENTS]',
                                    'bold',
                                    format_type))
        text.append('')
        text.append('Available actions:')
        for action in sorted(top_visible_actions, key=lambda x: x.name):
            text.append(cls.format_action_line(action.name,
                                               action.description,
                                               just,
                                               format_type))
        return '\n'.join(text)

    @classmethod
    def format_text(cls, text, format, format_type):
        """Formats text to have given format in given format_type.

        Args:
            text: text to format
            format: format, e.g. 'bold'
            format_type: None (will do nothing) or 'ascii'
        Returns:
            formatted text
        """
        if format_type == 'ascii':
            if format == 'bold':
                text = '\033[1m' + text + '\033[0m'
        return text

    @classmethod
    def format_action_line(cls, action_name, action_desc, just, format_type):
        """Creates and formats action line from given action_name and action_desc.

        Args:
            action_name: name of action
            action_desc: description of action
            just: columns to justify action_name to
            format_type: formats action_name in bold using this format, see
                         format_text help for available format types
        Returns:
            formatted action line
        """
        text = []
        justed_name = action_name.ljust(just)
        text.append(cls.format_text(justed_name, 'bold', format_type))
        text.append(action_desc)
        return ''.join(text)


class PkgInstallAction(Action):
    """Installs packages from Dapi"""
    name = 'install'
    description = 'Install packages'
    args = [argument.Argument('package', 'package', nargs='+')]

    @classmethod
    def run(cls, **kwargs):
        import os
        exs = []
        for pkg in kwargs['package']:
            logger.info('Installing {pkg}...'.format(pkg=pkg))
            if os.path.isfile(pkg):
                method = dapicli.install_dap_from_path
            else:
                method = dapicli.install_dap
            try:
                method(pkg)
                logger.info('{pkg} successfully installed'.format(pkg=pkg))
            except Exception as e:
                exs.append(str(e))
                logger.error(str(e))
        if exs:
            raise exceptions.ExecutionException('; '.join(exs))


class PkgUninstallAction(Action):
    """Uninstalls packages from Dapi"""
    name = 'uninstall'
    description = 'Uninstall packages'
    args = [
        argument.Argument('package', 'package', nargs='+'),
        argument.Argument('force', '-f', '--force', action='store_false',
                          default=True, help='Do not ask for confirmation')
    ]

    @classmethod
    def run(cls, **kwargs):
        exs = []
        for pkg in kwargs['package']:
            logger.info('Uninstalling {pkg}...'.format(pkg=pkg))
            try:
                done = dapicli.uninstall_dap(pkg, confirm=kwargs['force'])
                if done:
                    logger.info('{pkg} successfully uninstalled'.format(pkg=pkg))
            except Exception as e:
                exs.append(str(e))
                logger.error(str(e))
        if exs:
            raise exceptions.ExecutionException('; '.join(exs))


class PkgUpdateAction(Action):
    """Updates packages from Dapi"""
    name = 'update'
    description = 'Uninstall packages'
    args = [argument.Argument('package', 'package', nargs='*')]

    @classmethod
    def run(cls, **kwargs):
        pkgs = exs = []
        try:
            pkgs = kwargs['package']
        except KeyError:
            logger.info('Updating all packages')
            pkgs = dapicli.get_installed_daps()
        for pkg in pkgs:
            logger.info('Updating {pkg}...'.format(pkg=pkg))
            try:
                dapicli.install_dap(pkg,update=True)
                logger.info('{pkg} successfully updated'.format(pkg=pkg))
            except Exception as e:
                exs.append(str(e))
                logger.error(str(e))
        if exs:
            raise exceptions.ExecutionException('; '.join(exs))


class PkgListAction(Action):
    """List installed packages from Dapi"""
    name = 'list'
    description = 'List packages'

    @classmethod
    def run(cls, **kwargs):
        for pkg in dapicli.get_installed_daps():
            print(pkg)


class PkgSearchAction(Action):
    """Search packages from Dapi"""
    name = 'search'
    description = 'Search packages'
    args = [
        argument.Argument('query', 'query', nargs='+', help='One or multiple search queries'),
        argument.Argument('-p', '--page', metavar='P', type=int, default=1, help='Page number'),
    ]

    @classmethod
    def run(cls, **kwargs):
        try:
            dapicli.print_search(' '.join(kwargs['query']), kwargs['page'])
        except Exception as e:
            logger.error(str(e))
            raise exceptions.ExecutionException(str(e))


class PkgInfoAction(Action):
    """Prints information about packages from Dapi"""
    name = 'info'
    description = 'Prints packages info'
    args = [argument.Argument('package', 'package')]

    @classmethod
    def run(cls, **kwargs):
        try:
            dapicli.print_dap(kwargs['package'])
        except Exception as e:
            logger.error(str(e))
            raise exceptions.ExecutionException(str(e))


class PkgLintAction(Action):
    """Checks packages for sanity"""
    name = 'lint'
    description = 'Checks packages for sanity'
    args = [
        argument.Argument('package', 'package', nargs='+', help='One or multiple packages to check'),
        argument.Argument('network', '-n', '--network', action='store_true', default=False,
                          help='Perform checks that require Internet connection'),
        argument.Argument('nowarnings', '-w', '--nowarnings', action='store_true', default=False,
                          help='Ignore warnings'),
    ]

    @classmethod
    def run(cls, **kwargs):
        error = False
        for pkg in kwargs['package']:
            try:
                if kwargs['nowarnings']:
                    level = logging.ERROR
                else:
                    level = logging.INFO
                d = dapi.Dap(pkg)
                if not d.check(network=kwargs['network'], level=level):
                    error = True
            except (exceptions.DapFileError, exceptions.DapMetaError) as e:
                logger.error(str(e))
                error = True
        if error:
            raise exceptions.ExecutionException('One or more packages are not sane')



@register_action
class PkgAction(Action):
    """Installs packages from Dapi and more (removes, updates...)"""
    name = 'pkg'
    description = 'Manage packages'

    @classmethod
    def get_subactions(cls):
        return [
            PkgInstallAction,
            PkgUninstallAction,
            PkgUpdateAction,
            PkgListAction,
            PkgSearchAction,
            PkgInfoAction,
            PkgLintAction,
        ]


@register_action
class VersionAction(Action):
    """Prints DevAssistant version, what else?"""
    name = 'version'
    description = 'Print version'

    @classmethod
    def run(cls, **kwargs):
        from devassistant import __version__
        print('DevAssistant {version}'.format(version=__version__))
