#! /usr/bin/python3 -B

import os
import re
import sys


class dkms_item:
    module : str = ""
    version : str = ""
    modulename : str = ""
    debpath : str = ""
    apt_dkms : str = ""
    arch = []
    rprovides = []
    needs_off_series : bool = False

    def __init__(self, module, version):
        self.module = module
        self.version = version
        self.version = self.version.split(':')[-1]
        self.modulename = ""
        self.debpath = ""
        self.apt_dkms = ""
        self.arch = []
        # Flavour skipping works only with off_series packages, as in-series
        # are automatically built as part of the apt-install process
        self.skip_flavours = []
        self.rprovides = []
        # DEFAULT = FALSE
        # If True, manually download the .deb from a specified pool
        # If False, uses the apt Build-Depends mechanism
        self.needs_off_series = False

    def getKernelTargetDirectory(self):
        return self.modulename + "-" + self.version

    def getDebFilename(self):
        if self.debpath == "":
            raise OSError("No debpath is defined")
        filename = re.sub(r'%package%', self.module, self.debpath)
        filename = re.sub(r'%version%', self.version, filename)
        filename = os.path.basename(filename)
        return filename

    def getProvidedDkms(self):
        provides = ""
        for p in self.rprovides:
            provides += p + ", "
        return provides.strip().rstrip(',')

    def addModuleName(self, modulename):
        self.modulename = modulename

    def addArch(self, arch):
        self.arch.append(arch)

    def addSkipFlavours(self, flavour):
        self.skip_flavours.append(flavour)

    def addRprovides(self, rprovides):
        self.rprovides.append(rprovides)

    def addDebPath(self, debpath):
        self.debpath = debpath
        if (self.apt_dkms == ""):
            m = re.match(r".*\/(.*)_%version%.*.deb", debpath, re.X)
            if m:
                self.apt_dkms = m.group(1)

    def addAptDkms(self, aptdkms):
        self.apt_dkms = aptdkms

    def setNeedsManualBuild(self, status: bool):
        self.needs_off_series = status

    def printModule(self):
        print("Module: " + self.module)
        print("Version: " + self.version)
        print("ModuleName: " + self.modulename)
        tmp = ""
        for item in self.arch:
            tmp += item + " "
        print("Arch: " + tmp)
        tmp = ""
        for item in self.rprovides:
            tmp += item + " "
        print("rprovides: " + tmp)
        tmp = ""
        for item in self.skip_flavours:
            tmp += item + " "
        print("skip_flavours: " + tmp)
        print("debpath: " + self.debpath)
        print("apt_dkms: " + self.apt_dkms)
        print("needs_off_series: " + str(self.needs_off_series))

class transitional_item:
    module: str
    transition = []
    arch = []

    def __init__(self, module, version):
        self.module = module
        self.transition = []
        self.arch = ["all"]

    def addArch(self, arch):
        if "all" in self.arch:
            self.arch = []
        self.arch.append(arch)

    def addModuleName(self, module):
        self.modulename = module

    def addTransition(self, transition):
        self.transition.append(transition)

    def printTransition(self):
        print("Module: " + self.module)
        #print("Version: " + self.version)
        tmp = ""
        for item in self.arch:
            tmp += item + " "
        print("Arch: " + tmp)
        tmp = ""
        for item in self.transition:
            tmp += item + " "
        print("transition: " + tmp)


class dkms_modules:
    items : dkms_item = []
    transitions : transitional_item = []

    def get_arch_has_modules(self, arch):
        for item in self.items:
            if arch in item.arch:
                return True
        return False

    def parse_dkms(self, dkms_line: str):
        params = dkms_line.split(" ")
        tmp = dkms_item(params[0].replace("\n",""),
                        params[1].replace("\n",""))
        for parm in params[2:]:
            if parm.startswith("modulename="):
                tmp.addModuleName(parm.split("=")[1].replace("\n",""))
            elif parm.startswith("arch="):
                tmp.addArch(parm.split("=")[1].replace("\n",""))
            elif parm.startswith("rprovides="):
                tmp.addRprovides(parm.split("=")[1].replace("\n",""))
            elif parm.startswith("debpath="):
                tmp.addDebPath(parm.split("=")[1].replace("\n",""))
            elif parm.startswith("skip_flavour="):
                tmp.addSkipFlavours(parm.split("=")[1].replace("\n",""))
            elif parm.startswith("off_series="):
                status = parm.split("=")[1].replace("\n","")
                if status.lower() == 'true':
                    tmp.setNeedsManualBuild(True)
                else:
                    tmp.setNeedsManualBuild(False)
        self.items.append(tmp)

    def parse_transition(self, transition_line: str):
        params = transition_line.split(" ")
        tmp = transitional_item(params[0].replace("\n",""),
                                params[1].replace("\n",""))

        for parm in params[2:]:
            if parm.startswith("arch="):
                tmp.addArch(parm.split("=")[1].replace("\n",""))
            elif parm.startswith("transition="):
                tmp.addTransition(parm.split("=")[1].replace("\n",""))
        self.transitions.append(tmp)

    def parse_module(self, dkms_version_line: str):
        if "transition=" in dkms_version_line:
            self.parse_transition(dkms_version_line)
        else:
            self.parse_dkms(dkms_version_line)

    def print_modules(self):
        for item in self.items:
            item.printModule()
            print("")

    def print_transitions(self):
        for item in self.transitions:
            item.printTransition()
            print("")

    def return_prerequisites(self):
        res = ""
        length = len(self.items)
        for i, item in enumerate(self.items):
            res += " " + item.apt_dkms + " (= " + item.version + ") ["
            archs_len = len(item.arch)
            for j, arch in enumerate(item.arch):
                res += arch
                if (j < archs_len - 1):
                    res += " "
            res += "]"
            if i < length - 1:
                res += ",\n"

        return res


    def parse_dkms_version_file(self):
        self.items.clear()
        dkms_vf = open("debian/dkms-versions", "r")
        for item in dkms_vf:
            self.parse_module(item)

    # WARNING: DESTRUCTIVE PROCESS, deletes unrelated packages
    # Parse again if needs be
    def filter_per_architecture(self, architecture: str):
        self.items[:] = [x for x in self.items if architecture in x.arch]


    # WARNING: DESTRUCTIVE PROCESS, deletes unrelated packages
    # Parse again if needs be
    def filter_per_off_series(self):
        self.items[:] = [x for x in self.items if x.needs_off_series]

    # WARNING: DESTRUCTIVE PROCESS, deletes unrelated packages
    # Parse again if needs be
    def filter_per_build_depends_build(self):
        self.items[:] = [x for x in self.items if not x.needs_off_series]

# The following functions are used only for the manually built modules
def get_fake_dkms_root_folder():
    return os.path.join(
        os.getcwd(),
        "staging_dir",
        "linux-main-modules",
        "fake_dkms_root_folder",
        "")

def get_manual_dkms_build_folder():
    return os.path.join(
        os.getcwd(),
        "staging_dir",
        "linux-main-modules",
        "temp_dkms_build_folder",
        "")

def get_manual_dkms_output_folder():
    return os.path.join(
        os.getcwd(),
        "staging_dir",
        "linux-main-modules",
        "output_dkms",
        "")

# -----------------just for testing--------------------------------
#if __name__ == "__main__":
#    modules = dkms_modules()
#    modules.parse_dkms_version_file()
#    modules.filter_per_architecture("amd64")
#    modules.filter_per_off_series()
#    modules.print_modules()
#    modules.print_transitions()
