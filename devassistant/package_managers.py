# -*- coding: utf-8 -*-

from devassistant.command_helpers import RPMHelper, YUMHelper, PIPHelper, DialogHelper

from devassistant.logger import logger


class PackageManager(object):
    """ Abstract class for API definition of package managers """

    @classmethod
    def match(cls, *args, **kwargs):
        """
        Return True if this package manager should be chosen as dep installer
        """
        raise NotImplementedError()

    @classmethod
    def install(cls, *args, **kwargs):
        """ Install dependency """
        raise NotImplementedError()

    @classmethod
    def is_installed(cls, *args, **kwargs):
        """ Is dependency already installed? """
        raise NotImplementedError()

    @classmethod
    def resolve(cls, *args, **kwargs):
        """ Return all dependencies which will be installed """
        raise NotImplementedError()


class RPMPackageManager(PackageManager):
    """ Package manager for managing rpm packages from repositories """
    permission_prompt = "Install following packages?"

    @classmethod
    def match(cls, dep_t):
        return dep_t == 'rpm'

    @classmethod
    def install(cls, *args):
        return YUMHelper.install(*args)

    @classmethod
    def is_installed(cls, dep):
        logger.info("Checking for presence of %s", dep)
        if dep.startswith('@'):
            return YUMHelper.is_group_installed(dep)
        else:
            return RPMHelper.is_rpm_installed(dep)

    @classmethod
    def resolve(cls, *args):
        return YUMHelper.resolve(*args)

    def __str__(self):
        return "rpm package manager"


class PIPPackageManager(PackageManager):
    """ Package manager for managing python dependencies from PyPI """
    permission_prompt = "Install following packages from PyPI?"

    @classmethod
    def match(cls, dep_t):
        return dep_t == 'pip'

    @classmethod
    def install(cls, *dep):
        """ Install dependency """
        return PIPHelper.install(*dep)

    @classmethod
    def is_installed(cls, dep):
        logger.info("Checking for presence of %s", dep)
        return PIPHelper.is_egg_installed(dep)

    @classmethod
    def resolve(cls, *dep):
        # depresolver for PyPI is infeasable to do -- there are no structured
        # metadata for python packages; so just return this dependency
        # PIPHelper.resolve(dep)
        return dep

    def __str__(self):
        return "pip package manager"


class DependencyInstaller(object):
    """ class for installing dependencies """
    def __init__(self):
        # {PackageManagerClass: ['list', 'of', 'dependencies']}
        self.dependencies = {}

    def get_package_manager(self, dep_t):
        """ choose proper package manager and return it """
        # I admit that this is absolutely insane hack but it's the simplest
        # solution, also easy to maintain (no need to store list of package
        # managers somewhere)
        for glob in globals().itervalues():
            if isinstance(glob, type) and issubclass(glob, PackageManager):
                if glob.match(dep_t):
                    return glob

    def process_dependency(self, dep_t, dep_l):
        """ Add entry into self.dependencies """
        PackageManagerClass = self.get_package_manager(dep_t)
        self.dependencies.setdefault(PackageManagerClass, [])
        self.dependencies[PackageManagerClass].extend(dep_l)

    def ask_to_confirm(self, pac_man, *to_install):
        """ Return True if user wants to install packages, False otherwise """
        message = '\n'.join(sorted(to_install))
        ret = DialogHelper.ask_for_confirm_with_message(
            # TODO make this personalisable in pac man classes
            prompt=pac_man.permission_prompt,
            message=message,
        )
        return False if ret is False else True

    def install_dependencies(self):
        """ Install missing dependencies """
        for PackageManagerClass, deps in self.dependencies.iteritems():
            to_install = []
            for dep in deps:
                if not PackageManagerClass.is_installed(dep):
                    to_install.append(dep)
            if not to_install:
                # nothing to install, let's move on
                continue
            try:
                all_deps = PackageManagerClass.resolve(*to_install)
            except Exception as e:
                logger.error('Failed to resolve dependencies: {exc}'.format(exc=e))
                continue
            install = self.ask_to_confirm(PackageManagerClass, *all_deps)
            if install:
                installed = PackageManagerClass.install(*to_install)
                print 'installed:', installed
                logger.info("Successfully installed {0}".format(installed))

    def install(self, struct):
        """
        Call this like `DependencyInstaller(struct)` and it will figure out
        by itself which package manager to choose
        """
        #import ipdb ; ipdb.set_trace()
        for dep_dict in struct:
            for dep_t, dep_l in dep_dict.items():
                self.process_dependency(dep_t, dep_l)
        if self.dependencies:
            self.install_dependencies()


def main():
    """ just for testing """

    di = DependencyInstaller()
    di.install([{'rpm': ['python-celery']}, {'pip': ['scipy', 'celery']}])

if __name__ == '__main__':
    main()
