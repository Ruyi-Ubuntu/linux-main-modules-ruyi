#! /usr/bin/python3 -B

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

from dkms_helper import (dkms_modules, get_manual_dkms_output_folder)
from flavour_finder import find_flavours_from_arch


def copy_ko_files_in_tar_folder(module:str, signing_dir_version: str,
                                ko_modules_dir: str):
    module_dir = signing_dir_version + "/" + module
    os.makedirs(module_dir, exist_ok=True)
    for file in os.listdir(ko_modules_dir):
        if file.endswith(".ko"):
            print("DDD --- Copy: " + ko_modules_dir + "/" + file)
            shutil.copy(ko_modules_dir + "/" + file, module_dir + "/" + file)
        # Some installations seems to use DKMS compression, others don't, so
        # check both cases
        elif file.endswith(".ko.zst"):
            print("DDD --- Decomp/copy: " + ko_modules_dir + "/" + file)
            decompressed_file=file.replace(".zst", "")
            with tempfile.TemporaryDirectory() as tmpdir:
                zstd_command = [ "zstd", "-d", ko_modules_dir + "/" + file,
                                "-o", tmpdir + "/" + decompressed_file]
                decompress = subprocess.run(zstd_command,
                              stdout = subprocess.PIPE,
                              stderr = subprocess.PIPE,
                              check = True,
                              text = True)
                shutil.copy(tmpdir + "/" + decompressed_file, module_dir + "/" + decompressed_file)
        else:
            print("DDD --- Unknown file " + file + " Found in ko directory...skipping")


def find_path_build_depends_kos(module, kernel_abi: str, kernel_flavour: str):
    dkms_build_pattern = os.path.join(
            "/var/lib/dkms/",
            module.modulename,
            "*",
            kernel_abi + "-" + kernel_flavour,
            "*",
            "module"
    )
    dkms_build_pattern_noname = os.path.join(
            "/var/lib/dkms/",
            module.module,
            "*",
            kernel_abi + "-" + kernel_flavour,
            "*",
            "module"
    )

    print(f"DDD: Matching patterns: {dkms_build_pattern} / {dkms_build_pattern_noname}")
    matches = glob.glob(dkms_build_pattern)
    if not matches:
        matches = glob.glob(dkms_build_pattern_noname)
        if not matches:
            raise OSError("Could not find DKMS build artifacts at: " + dkms_build_pattern)
    build_dir = matches[0]
    return build_dir

def prepare_per_flavour(deb_host_arch:str, kernel_version: str,
                        kernel_abi: str, signing_dir: str, flavour: str):
    modules = dkms_modules()
    modules.parse_dkms_version_file()
    modules.filter_per_architecture(deb_host_arch)

    signing_dir_version = signing_dir + "/" + kernel_version
    os.makedirs(signing_dir_version, exist_ok=True)

    for module in modules.items:
        print("DDD - Copying " + module.modulename + " - " + kernel_abi + "-" + flavour)
        ko_src_modules_dir = ""
        ko_dst_module_dir = flavour + "/" + module.getKernelTargetDirectory()

        if not module.needs_off_series:
            # Build-Depends modules path
            print("DDD - Build-depends copy procedure")
            try:
                ko_src_modules_dir = find_path_build_depends_kos(module, kernel_abi, flavour)
            except:
                print("------------------------WARNING------------------------")
                print("------------------------WARNING------------------------")
                print("WARNING: No modules built for the " + flavour + " flavour: skipping copy phase")
                print("------------------------WARNING------------------------")
                print("------------------------WARNING------------------------")
                continue
        else:
            # Manually built modules path
            print("DDD - Off-series copy procedure")
            faketree_src_modules_dir = "/lib/modules/" + kernel_abi + "-" + flavour + "/updates/dkms/"
            ko_src_modules_dir = get_manual_dkms_output_folder() + faketree_src_modules_dir
            ko_src_modules_dir += module.getKernelTargetDirectory()
            if not os.path.exists(ko_src_modules_dir):
                print("------------------------WARNING------------------------")
                print("------------------------WARNING------------------------")
                print("WARNING: No modules built for the " + flavour + " flavour: skipping copy phase")
                print("------------------------WARNING------------------------")
                print("------------------------WARNING------------------------")
                continue

        copy_ko_files_in_tar_folder(ko_dst_module_dir,
                                    signing_dir_version,
                                    ko_src_modules_dir)



def main(deb_host_arch:str, kernel_version: str,
         signing_dir: str, kernel_abi: str):
    flavours = find_flavours_from_arch(deb_host_arch)
    flav_text = ""
    for flavour in flavours:
        flav_text += flavour + " "
    print("[dkms-archive.py] Running with the following parameters:")
    print("   deb_host_arch  = " + deb_host_arch)
    print("   kernel_version = " + kernel_version)
    print("   kernel_abi     = " + kernel_abi)
    print("   signing_dir    = " + signing_dir)
    print("   flavours       = " + flav_text)

    for flavour in flavours:
        prepare_per_flavour(deb_host_arch, kernel_version,
                            kernel_abi, signing_dir, flavour)

# --------------------------------------------------------------------
# deb_host_arh: the archoitecture we are building for (amd64, arm64...)
# kernel_version: the full kernel version (6.8.0-88.89+52)
# signing_dir: the directory whre the ko files will be saved (/SIGNING)
# ko_modules_dir: where the ko files have been built
#               (/lib/modules/$(kernel_version)/updates/dkms/)
(arg_deb_host_arch, arg_kernel_version,
 arg_signing_dir, arg_kernel_abi) = sys.argv[1:]
main(arg_deb_host_arch, arg_kernel_version, arg_signing_dir, arg_kernel_abi)
