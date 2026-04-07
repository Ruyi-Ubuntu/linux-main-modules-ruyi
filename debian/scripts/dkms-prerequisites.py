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

def insert_requirements_in_control_file(modules, kernel_abi_version: str,
                                        kernel_main_version:str, flavours: List[str]):
    res = ""
    for flavour in flavours:
        res += " linux-" + flavour.flavour + "-headers-" + kernel_abi_version
        res += " (>= " + kernel_main_version + ") "
        res += " ["
        archs_size = len(flavour.archs)
        for i, arch in enumerate(flavour.archs):
            res += arch
            if i < archs_size - 1:
                res += " "
        res += "],\n"

    prereqs = modules.return_prerequisites()

    if not prereqs == "":
        res += prereqs
    else:
        res = res.rstrip("\n").rstrip(",")


    final_control = ""
    with open("debian/control", "r") as src:
        control = src.read()
        final_control = re.sub("@DKMS-DEPENDS@", res, control)
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
