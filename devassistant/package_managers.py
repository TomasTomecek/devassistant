# -*- coding: utf-8 -*-

from devassistant.command_helpers import RPMHelper, YUMHelper, PIPHelper


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

    @classmethod
    def match(cls, dep_t):
        return dep_t == 'rpm'

    @classmethod
    def install(cls, *args, **kwargs):
        return

    @classmethod
    def is_installed(cls, dep):
        if dep.startswith('@'):
            return YUMHelper.is_group_installed(dep)
        else:
            return RPMHelper.is_rpm_installed(dep)

    @classmethod
    def resolve(cls, *args, **kwargs):
        raise NotImplementedError()


class PIPPackageManager(PackageManager):
    """ Package manager for managing python dependencies from PyPI """
    command = 'pip'

    @classmethod
    def match(cls, dep_t):
        return dep_t == 'pip'

    @classmethod
    def install(cls, *args, **kwargs):
        """ Install dependency """
        raise NotImplementedError()

    @classmethod
    def is_installed(cls, dep):
        return PIPHelper.is_egg_installed(dep)

    @classmethod
    def resolve(cls, dep):
        return PIPHelper.resolve(dep)

class DependencyInstaller(object):

    def __init__(self):
        # {PackageManagerClass: ['list', 'of', 'dependencies']}
        self.dependencies = {}

    def get_package_manager(self, dep_t):
        """ choose proper package manager and return it """
        # I admit that this is absolutely insane hack but it's most easiest
        # to be done, also easy to maintain (no need to store list of package
        # managers somewhere)
        for glob in globals().itervalues():
            if isinstance(glob, type) and issubclass(glob, PackageManager):
                if glob.match(dep_t):
                    print glob
                    return glob

    def process_dependency(self, dep_t, dep_l):
        """ Add entry into self.dependencies """
        PackageManagerClass = self.get_package_manager(dep_t)
        self.dependencies.setdefault(PackageManagerClass, [])
        self.dependencies[PackageManagerClass].extend(dep_l)

    def install_dependencies(self):
        """ Install missing dependencies """
        for PackageManagerClass, deps in self.dependencies.iteritems():
            for dep in deps:
                if not PackageManagerClass.is_installed(dep):
                    print dep, 'is not installed'
                    PackageManagerClass.resolve(dep)
                    PackageManagerClass.install(dep)

    def install(self, struct):
        """
        Call this like `DependencyInstaller(struct)` and it will figure out
        by itself which package manager to choose
        """
        #import ipdb ; ipdb.set_trace()
        print struct
        for dep_dict in struct:
            for dep_t, dep_l in dep_dict.items():
                self.process_dependency(dep_t, dep_l)
        if self.dependencies:
            print self.dependencies
            self.install_dependencies()


def main():
    """ just for testing """

    di = DependencyInstaller()
    di.install([{'pip': ['numpy']}, {'pip': ['scipy']}])

if __name__ == '__main__':
    main()