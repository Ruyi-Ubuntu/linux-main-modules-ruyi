#! /usr/bin/python3 -B

import os
import re
import shutil
import sys
if sys.version_info >= (3, 9):
    List = list
else:
    from typing import List

from dkms_helper import dkms_modules
from flavour_finder import find_flavours

def create_depends_from_prefix(module_prefix:str, kernel_abi_version: str,
                               kernel_main_version:str, flavours: List[str]) -> str:
    res = ""
    flavour_size = len(flavours)
    for flavour_number, flavour in enumerate(flavours):
        res += " " + module_prefix + kernel_abi_version + "-" + flavour.flavour
        res += " (>= " + kernel_main_version + ") "
        res += " ["
        archs_size = len(flavour.archs)
        for i, arch in enumerate(flavour.archs):
            res += arch
            if i < archs_size - 1:
                res += " "
        if flavour_number < flavour_size - 1:
            res += "],\n"
        else:
            res += "]"
    return res

def insert_requirements_in_control_file(modules, kernel_abi_version: str,
                                        kernel_main_version:str, flavours: List[str]):
    # Synthetic dependency to force the LMM package to not promote before the
    # main kernel
    res_synthetic_depends = create_depends_from_prefix("linux-modules-",
                                                       kernel_abi_version,
                                                       kernel_main_version,
                                                       flavours)

    # Headers dependencies for each flavour/architecture
    res_build_depends = create_depends_from_prefix("linux-headers-",
                                                   kernel_abi_version,
                                                   kernel_main_version,
                                                   flavours)


    prereqs = modules.return_prerequisites()
    if not prereqs == "":
        res_build_depends += ", \n" + prereqs
    else:
        res_build_depends = res_build_depends.rstrip("\n").rstrip(",")


    final_control = ""
    with open("debian/control", "r") as src:
        control = src.read()
        final_control = re.sub("@DKMS-DEPENDS@", res_build_depends, control)
        final_control = re.sub("@SYNTHETIC-DEPENDS@", res_synthetic_depends, final_control)
    with open("debian/control.tmp", "w") as dst:
        dst.write(final_control)
    shutil.move("debian/control.tmp", "debian/control")


# ------------------------------------------------------
(kernel_abi_version, kernel_main_version) = sys.argv[1:]
modules = dkms_modules()

modules.parse_dkms_version_file()
modules.filter_per_build_depends_build()
# For Debugging purposes
#print("\nModules to be produced:")
#modules.print_modules()
flavours = find_flavours()
insert_requirements_in_control_file(modules, kernel_abi_version, kernel_main_version, flavours)
