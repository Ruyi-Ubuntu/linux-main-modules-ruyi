#! /usr/bin/python3 -B

import re
import sys
import shutil

from dkms_helper import dkms_modules
from flavour_finder import find_flavours
from variant_helper import find_variants

if sys.version_info >= (3, 9):
    List = list
else:
    from typing import List


PACKAGE_BASE_NAME="linux-main-modules"

default_package_template = """
Package: """ + PACKAGE_BASE_NAME + """-@DKMS_NAME@@UNSIGNED@-@KERNEL_ABI@-@KERNEL_FLAVOUR@
Build-Profiles: <!stage1>
Architecture: @ARCHITECTURE@
Section: kernel
Priority: optional
@PROVIDES@
Depends: ${misc:Depends}, ${shlibs:Depends}, kmod, linux-image-@ABI@-@KERNEL_FLAVOUR@ | linux-image-unsigned-@ABI@-@KERNEL_FLAVOUR@
Description: @SIGNED_STATUS@ @DKMS_NAME@ module for @KERNEL_ABI@
 This package contains the signed @DKMS_NAME@ modules.
 .
 You likely do not want to install this package directly, Instead, install
 the linux-@DKMS_NAME@-@KERNEL_FLAVOUR@ meta-package, which will ensure that
 upgrades work correctly, and that supporting packages are also installed.
"""

default_variant_package_template = """
Package: linux-modules-@DKMS_NAME@@UNSIGNED@-@KERNEL_FLAVOUR@@KERNEL_VARIANT@
Build-Profiles: <!stage1>
Architecture: @ARCHITECTURE@
Section: kernel
Priority: optional
Depends: ${misc:Depends}, ${shlibs:Depends}, kmod, """ + PACKAGE_BASE_NAME + """-@DKMS_NAME@@UNSIGNED@-@KERNEL_ABI@-@KERNEL_FLAVOUR@
Description: Extra drivers for @DKMS_NAME@ for the @KERNEL_FLAVOUR@ flavour
 Install extra signed @DKMS_NAME@ modules compatible with the @KERNEL_FLAVOUR@ flavour
"""

default_transitional_package_template = """
Package: linux-modules-@DKMS_OLD_NAME@-@KERNEL_FLAVOUR@@KERNEL_VARIANT@
Architecture: @ARCHITECTURE@
Section: oldlibs
Depends: linux-modules-@DKMS_NEW_NAME@-@KERNEL_FLAVOUR@@KERNEL_VARIANT@
Description: Extra drivers for @DKMS_OLD_NAME@-@KERNEL_FLAVOUR@@KERNEL_VARIANT@
 (dummy transitional package)
 Transitional package for upgrades of @DKMS_OLD_NAME@ to [@ARCHITECTURE@]
"""


def create_new_variant_package(dkms_name:str, archs:str, kernel_flavour:str, kernel_abi:str, unsigned_prefix:str):
    control_variants=""
    variants = find_variants()
    for variant in variants:
        template = default_variant_package_template
        template = re.sub("@DKMS_NAME@", dkms_name, template)
        template = re.sub("@KERNEL_ABI@", kernel_abi, template)
        template = re.sub("@KERNEL_FLAVOUR@", kernel_flavour, template)
        template = re.sub("@ARCHITECTURE@", archs, template)
        template = re.sub("@KERNEL_VARIANT@", variant, template)
        template = re.sub("@UNSIGNED@", unsigned_prefix, template)
        template += "\n"
        control_variants+=template
    return control_variants


def intersect_archs(kernel_archs: List[str], dkms_archs: List[str]):
    res = ""
    for k_arch in kernel_archs:
        if k_arch in dkms_archs:
            if k_arch not in res:
                res += k_arch + " "
    return res.strip()


def create_new_packages(modules, kernel_arch: str,
                        kernel_abi: str, kernel_flavours: List[str],
                        is_signed: bool):
    if not is_signed:
        unsigned_prefix = "-unsigned"
        signed_status = "Unsigned"
    else:
        unsigned_prefix = ""
        signed_status = "Signed"
    full_template = "\n"
    for kernel_flavour in kernel_flavours:
        for item in modules.items:
            if kernel_flavour in item.skip_flavours:
                print(f"Skipping {item.modulename} for {kernel_flavour}")
                continue
            archs = intersect_archs(kernel_flavour.archs, item.arch)
            # If no architectures in common between DKMS and flavour, just skip
            if archs == "":
                continue
            template = default_package_template
            template = re.sub("@DKMS_NAME@", item.modulename, template)
            template = re.sub("@KERNEL_ABI@", kernel_abi, template)
            template = re.sub("@KERNEL_FLAVOUR@", kernel_flavour.flavour, template)
            template = re.sub("@ARCHITECTURE@", archs, template)
            template = re.sub("@UNSIGNED@", unsigned_prefix, template)
            template = re.sub("@SIGNED_STATUS@", signed_status, template)
            provides = item.getProvidedDkms()
            if not is_signed:
                signed_package = (PACKAGE_BASE_NAME + "-" + item.modulename + "-" +
                                  kernel_abi + "-" + kernel_flavour.flavour)
                if provides:
                    provides += ", "
                provides += signed_package
            if provides:
                template = re.sub("@PROVIDES@", "Provides: " + provides, template)
            else:
                template = re.sub("@PROVIDES@\n", "", template)
            template += "\n"
            full_template += template
            ##### This part is only for the variant, to be removed in the future
            full_template += create_new_variant_package(item.modulename,
                                                        archs,
                                                        kernel_flavour.flavour,
                                                        kernel_abi,
                                                        unsigned_prefix)
            ####################################################################
    return full_template


def create_transitional_packages(full_template: str, modules, kernel_arch: str,
                        kernel_abi: str, kernel_flavours: List[str]):
    variants = find_variants()
    for kernel_flavour in kernel_flavours:
        for item in modules.transitions:
            for variant in variants:
                archs = intersect_archs(kernel_flavour.archs, item.arch)
                if "all" in item.arch:
                    archs = "all"
                # If no architectures in common between DKMS and flavour, just skip
                if archs == "":
                    continue
                for transition in item.transition:
                    template = default_transitional_package_template
                    template = re.sub("@DKMS_OLD_NAME@", transition, template)
                    template = re.sub("@DKMS_NEW_NAME@", item.module, template)
                    template = re.sub("@KERNEL_ABI@", kernel_abi, template)
                    template = re.sub("@KERNEL_FLAVOUR@", kernel_flavour.flavour, template)
                    template = re.sub("@KERNEL_VARIANT@", variant, template)
                    template = re.sub("@ARCHITECTURE@", archs, template)
                    template += "\n"
                    full_template += template
    return full_template


def create_temporary_stub_file(pkgs_dkms_modules: str, is_signed: bool):
    control_file = ""
    if is_signed:
        with open("debian/control.stub", "r") as src:
            control_file = src.read()
    with open("debian/control.stub.tmp", "w") as dst:
        control_file += pkgs_dkms_modules
        dst.write(control_file)


# ------------------------------------------------------------
(arg_deb_host_arch, arg_kernel_abi, sign_mode) = sys.argv[1:]
modules = dkms_modules()

modules.parse_dkms_version_file()

flavours = find_flavours()
if sign_mode == "unsigned":
    is_signed = False
else:
    is_signed = True
pkgs_dkms_modules = create_new_packages(modules, arg_deb_host_arch,
                                        arg_kernel_abi, flavours, is_signed)
if is_signed:
    pkgs_dkms_modules = create_transitional_packages(pkgs_dkms_modules,
                                            modules, arg_deb_host_arch,
                                            arg_kernel_abi, flavours)
create_temporary_stub_file(pkgs_dkms_modules, is_signed)
