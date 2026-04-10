#! /usr/bin/python3 -B

import os
import subprocess
import sys
import re

from dkms_helper import dkms_modules
from flavour_finder import find_flavours_from_arch


# Concatenate the ko file with the signature
def sign_file(src_file: str):
    signature_file = src_file + ".sig"
    with open(src_file, "ab") as f_src:
        with open(signature_file, "rb") as f_sig:
            f_src.write(f_sig.read())


def compress_file(ko_file: str):
    zstd_command = [ "zstd", "-q", "-3", ko_file, "-o", ko_file + ".zst"]
    compress = subprocess.run(zstd_command,
                              stdout = subprocess.PIPE,
                              stderr = subprocess.PIPE,
                              check = True,
                              text = True)

def build_package_name(module_name: str, abi: str, flavour:str):
    return "linux-main-modules-" + module_name + "-" + abi + "-" + flavour


def append_module_in_debian_install(module_name: str, module: str,
                                    module_full_path: str, abi: str,
                                    flavour: str):
    package = build_package_name(module_name, abi, flavour)
    print(package + ": adding " + module + " [" + module_full_path + "]")
    with open("debian/" + package + ".install", "a") as deb_install_file:
        entry = module_full_path + " "
        entry += "/lib/modules/" + abi + "-" + flavour + "/kernel/" + module_name + "\n"
        deb_install_file.write(entry)


def get_module_name_from_directory(dir_name: str):
    kernel_modules = dkms_modules()
    kernel_modules.parse_dkms_version_file()
    for module in kernel_modules.items:
        if dir_name == module.getKernelTargetDirectory():
            return module.modulename
    print("=========================WARNING============================")
    print("=========================WARNING============================")
    print("=========================WARNING============================")
    print("Something went wrong with the folder naming scheme for ")
    print("module: " + dir_name)
    print("Please check dkms-versions is correct ")
    print("Will try to go with fallback logic")
    print("=========================WARNING============================")
    print("=========================WARNING============================")
    print("=========================WARNING============================")
    if "-" in dir_name:
        return dir_name.split("-")[0]
    return dir_name

def copy_files(version: str, abi:str, flavour: str):
    modules_to_install = []
    # If this fails, something went really wrong during upstream signing
    folders = os.listdir(version + "/" + flavour)
    for folder in folders:
        module_dir = version + "/" + flavour + "/" + folder
        if not os.path.isdir(module_dir):
            continue
        module_name = get_module_name_from_directory(folder)
        modules_to_install.append(module_name)
        files = os.listdir(module_dir)
        for module in files:
            if module.endswith(".ko"):
                module_path = module_dir + "/" + module
                sign_file(module_path)
                compress_file(module_path)
                append_module_in_debian_install(module_name,
                                                module,
                                                module_path + ".zst",
                                                abi,
                                                flavour)
    return modules_to_install


def install_post_files(modules_to_install: list[str], arch: str,
                 abi: str, flavour: str):
    instfile = "vmlinuz"
    if arch == "ppc64el":
        instfile = "vmlinux"
    for module_name in modules_to_install:
        package_name = build_package_name(module_name, abi, flavour)
        post_cmds = ["postinst", "postrm"]
        for cmd in post_cmds:
            dst_content = ""
            src_file = "debian/templates/" + cmd + ".in"
            dst_file = "debian/" + package_name + "." + cmd
            with open(src_file, "r") as fp_src:
                dst_content = fp_src.read()
                dst_content = re.sub("@abiname@", abi, dst_content)
                dst_content = re.sub("@localversion@", flavour, dst_content)
                dst_content = re.sub("@image-stem@", instfile, dst_content)
            with open(dst_file, "w") as fp_dst:
                fp_dst.write(dst_content)
            print("Created " + dst_file)

# -----------------------------------------------------------------------

(arg_arch, arg_version, arg_abi) = sys.argv[1:]
flavours = find_flavours_from_arch(arg_arch)
flav_text= ""
for flavour in flavours:
    flav_text += flavour + " "
print("auto_install.py: INFO - Running with the following parameters:" + \
            "\narch: " + arg_arch + \
            "\nversion: " + arg_version + \
            "\nabi: " + arg_abi + \
            "\nflavours " + flav_text)

kernel_modules = dkms_modules()
kernel_modules.parse_dkms_version_file()
if kernel_modules.get_arch_has_modules(arg_arch):
    for flavour in flavours:
        modules_to_install = copy_files(arg_version, arg_abi, flavour)
        install_post_files(modules_to_install, arg_arch, arg_abi, flavour)
