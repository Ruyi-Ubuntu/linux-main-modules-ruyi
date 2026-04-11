#! /usr/bin/python3 -B

import errno
import glob
import os
import re
import shutil
import subprocess
import sys

from dkms_helper import (
        dkms_modules,
        get_fake_dkms_root_folder,
        get_manual_dkms_build_folder,
        get_manual_dkms_output_folder)


LAUNCHPAD_LIBRARIAN_URL = "https://launchpad.net/ubuntu/+archive/primary/+files/"


def get_module_partial_url(module):
    url = module.debpath
    url = re.sub(r'%package%', module.module, url)
    url = re.sub(r'%version%', module.version, url)
    return url


def download_file(full_url: str, filename: str):
    print("D --- Trying to download from " + full_url)
    cmd = ["wget", "-q", "--show-progress",
           "-O", get_manual_dkms_build_folder() + "/" + filename,
           "--tries=3", "--continue", full_url]

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"Wget failed to download {full_url}")
        return False


def get_apt_pool_urls():
    pool_urls = set()
    sources_paths = ['/etc/apt/sources.list']

    if os.path.isdir('/etc/apt/sources.list.d'):
        for f in os.listdir('/etc/apt/sources.list.d'):
            if f.endswith(('.list', '.sources')):
                sources_paths.append(os.path.join('/etc/apt/sources.list.d', f))

    for path in sources_paths:
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    # 1. Handle standard .list files (deb http://...)
                    if line.startswith(('deb ', 'deb-src ')):
                        parts = line.split()
                        # Find the first part that starts with http
                        for part in parts:
                            if part.startswith(('http://', 'https://')):
                                url = part.rstrip('/')
                                pool_urls.add(f"{url}")
                                break

                    # 2. Handle .sources files (URIs: http://...)
                    elif line.startswith('URIs:'):
                        # Split by space in case there are multiple URIs on one line
                        uris = line.replace('URIs:', '').strip().split()
                        for uri in uris:
                            if uri.startswith(('http://', 'https://')):
                                url = uri.rstrip('/')
                                pool_urls.add(f"{url}")

        except Exception as e:
            print(f"Could not read {path}: {e}")

    # Final filter: ensure we didn't pick up any stray bracket leftovers
    return sorted([u for u in pool_urls if u.startswith(('http', 'https'))])


def download_module(module):
    url = get_module_partial_url(module)
    filename = module.getDebFilename()
    if url.startswith("pool"):
        full_url = LAUNCHPAD_LIBRARIAN_URL + filename
        result = download_file(full_url, filename)
        if result:
            return True

        print("EEE --- Failed to download from Launchpad Librarian...")
        pools = get_apt_pool_urls()
        for p in pools:
            result = download_file(p + "/" + url, filename)
            if result:
                return True
        print("EEE --- Failed to download....check the debpath in dkms-versions")
        return False
    return False


def get_module_extracted_directory(module):
    return module.modulename + "-" + module.version


def extract_debian_package(module):
    filename = module.getDebFilename()
    source_deb = get_manual_dkms_build_folder() + "/" + filename
    destination_folder = get_manual_dkms_build_folder() + "/" + get_module_extracted_directory(module)
    print("D ---Extracting " + source_deb + " into " + destination_folder)
    extract_command = ["dpkg", "-x", source_deb, destination_folder]
    try:
        subprocess.run(extract_command, check=True)
        return True
    except subprocess.CalledProcessError:
        print("EEE --- Something went wrong during decompression...bailing")
        return False
    return True


def find_and_parse_dkms(extracted_root):
    metadata = {'name': None, 'version': None, 'source_dir': None}
    found_conf = False

    # 1. Recursive search
    for root, dirs, files in os.walk(extracted_root):
        if "dkms.conf" in files:
            found_conf = True
            metadata['source_dir'] = root
            conf_path = os.path.join(root, "dkms.conf")

            try:
                with open(conf_path, 'r') as f:
                    content = f.read()

                    # Regex for PACKAGE_NAME and PACKAGE_VERSION
                    name_match = re.search(r'PACKAGE_NAME=["\']?([^"\']+)["\']?', content)
                    version_match = re.search(r'PACKAGE_VERSION=["\']?([^"\']+)["\']?', content)

                    if name_match:
                        metadata['name'] = name_match.group(1).strip()
                    if version_match:
                        metadata['version'] = version_match.group(1).strip()

                # Exit the loop once we find the first valid dkms.conf
                break
            except Exception as e:
                print(f"EEE - Permission denied reading {conf_path}: {e}")

    # 2. Raise OSError if the loop finished without finding anything
    if not found_conf:
        raise OSError(
            errno.ENOENT,
            "No 'dkms.conf' found in the extracted path. Is this a DKMS package?",
            extracted_root
        )

    return metadata


def add_dkms_to_fakeroot(module):
    extracted_folder = get_module_extracted_directory(module)
    metadata = find_and_parse_dkms(get_manual_dkms_build_folder() + "/" + extracted_folder)
    module_name = metadata['name']
    module_version = metadata['version']
    my_env = os.environ.copy()
    my_env["CONFIG_MODULE_SIG"] = "n"
    my_env["CONFIG_MODULE_SIG_ALL"] = "n"

    print("DDD --- Add " + module_name + "-" + module_version)
    dkms_add_command = ["dkms", "add",
                        "-m", module_name,
                        "-v", module_version,
                        "--dkmstree",  get_fake_dkms_root_folder(),
                        "--sourcetree", get_manual_dkms_build_folder() + extracted_folder + "/usr/src/"  ]
    try:
        subprocess.run(dkms_add_command, check=True, env=my_env)
        return True
    except subprocess.CalledProcessError:
        print("EEE --- Cannot add the DKMS to the fakeroot...bailing...")
        return False
    return True


def lib_symlink_exists() -> bool:
    path = "/lib/modules"
    if not os.path.exists(path):
        return False
    return True


def usr_lib_modules_exists() -> bool:
    path = "/usr/lib/modules"
    if not os.path.exists(path):
        return False
    return True


def usr_src_exists() -> bool:
    path = "/usr/src"
    if not os.path.exists(path):
        return False
    return True


def is_valid_usr_src_kernel(kernel: str) -> bool:
    if not "linux-headers-" in kernel:
        return False
    config_path = os.path.join("/usr/src/", kernel, ".config")
    if os.path.isfile(config_path):
        return True
    return False


def get_installed_kernels():
    base_path = "/lib/modules"
    if not lib_symlink_exists():
        print("EEE: No /lib/modules folder?????")
        base_path = "/usr/lib/modules"
        if not usr_lib_modules_exists():
            print("EEE: No /usr/lib/modules folder either?????")
            base_path = "/usr/src" 
            if not usr_src_exists():
                print("EEE: No /usr/src folder...giving up")
                raise OSError("Can't proceed, just fully FAIL")

    print(f"DDD: using path {base_path}")
    kernels_with_build = []
    debug_print_usr_src = False
    for k in os.listdir(base_path):
        if base_path == "/usr/src":
            if not is_valid_usr_src_kernel(k):
                print(f"DDD: {k} not a valid kernel folder")
                continue

        full_path = os.path.join(base_path, k)
        if base_path == "/usr/src":
            build_link = full_path
            source_dir = full_path
        else:
            build_link = os.path.join(full_path, 'build')
            source_dir = os.path.join("/usr/src/", "linux-headers-" + k)

        if os.path.isdir(build_link):
            kernels_with_build.append(k)
            print(f"[OK] Found kernel {k}, adding to buildspec")
        else:
            print(f"[WARNING] Found kernel {k}, but 'build' folder is missing or broken.")
            debug_print_usr_src = True
            if os.path.isdir(source_dir):
                print(f"  --> Strange, {source_dir} exists. Link has not been correctly created?")

    if debug_print_usr_src:
        print("")
        print("==================")
        print("DDD: Printing all in /usr/src")
        for source in os.listdir("/usr/src"):
            print(f"DDD: Found source {source}")
        print("==================")
        print("")

    return kernels_with_build


def relocate_modules(fakeroot: str, module_name: str, module_version: str,
                     module_kernel_target_directory: str,
                     kernel_version: str, dkms_conf_path: str):
    """
    Finds built modules in the DKMS tree using wildcards for architecture
    and relocates them to a standard kernel module tree inside a fakeroot.
    """
    # 1. Use '*' as a wildcard for the architecture directory
    # This handles the amd64 vs x86_64 discrepancy automatically
    dkms_build_pattern = os.path.join(
        get_fake_dkms_root_folder(),
        module_name, module_version, kernel_version, "*", "module"
    )

    # 2. Find the actual build directory
    matches = glob.glob(dkms_build_pattern)
    if not matches:
        print(f"WARNING: Could not find DKMS build artifacts at: {dkms_build_pattern}")
        raise os.OSError(f"WARNING: Could not find DKMS build artifacts at: {dkms_build_pattern}")

    # Take the first architecture match found
    build_dir = matches[0]

    # 3. Create the destination tree in the fakeroot
    # Standard: <fakeroot>/lib/modules/<kernel>/updates/dkms/module_name/
    target_dir = os.path.join(fakeroot, "lib/modules", kernel_version,
                              "updates/dkms/", module_kernel_target_directory)
    os.makedirs(target_dir, exist_ok=True)

    print(f"Source: {build_dir}")
    print(f"Target: {target_dir}")

    # 4. Relocate every .ko file (including compressed versions like .zst or .gz)
    # We use shutil.copy2 to preserve metadata/timestamps
    for file_path in glob.glob(os.path.join(build_dir, "*.ko*")):
        filename = os.path.basename(file_path)
        dest_path = os.path.join(target_dir, filename)

        shutil.copy2(file_path, dest_path)
        print(f"  Relocated: {filename}")


def print_dkms_build_log(module_name: str, module_version: str, kernel: str):
    dkms_dir = get_fake_dkms_root_folder()
    patterns = [
            os.path.join(dkms_dir, module_name, module_version, kernel, "*", "log", "make.log"),
            os.path.join(dkms_dir, module_name, module_version, "build", "make.log")
    ]

    log_files = []
    for pattern in patterns:
        log_files.extend(glob.glob(pattern))

    for log in log_files:
        print("DDD ------------------------------------------------------")
        print(f"DDD ---------Content of {log}----------------------------")
        print("DDD ------------------------------------------------------")
        with open(log, 'r', errors='replace') as f:
            for line in f:
                print(line.rstrip())
        print("DDD ------------------------------------------------------")
        print(f"DDD ------END Content of {log}---------------------------")
        print("DDD ------------------------------------------------------")
        print("")
        print("")
        print("")

def should_skip(module, kernel):
    for flavour_to_skip in module.skip_flavours:
        if kernel.endswith(flavour_to_skip):
            return True
    return False


def build_dkms_in_fakeroot(module):
    kernels = get_installed_kernels()
    extracted_folder = get_module_extracted_directory(module)
    metadata = find_and_parse_dkms(get_manual_dkms_build_folder() + "/" + extracted_folder)
    module_name = metadata['name']
    module_version = metadata['version']
    dkms_conf_path = metadata['source_dir'] + "/dkms.conf"
    my_env = os.environ.copy()
    my_env["CONFIG_MODULE_SIG"] = "n"
    my_env["CONFIG_MODULE_SIG_ALL"] = "n"

    for kernel in kernels:
        # /usr/src corner case
        if "linux-headers-" in kernel:
            kernel = kernel.strip("linux-headers-")
        if should_skip(module, kernel):
            print(f"DDD: Skipping module:{module_name} for kernel:{kernel}")
            continue
        print("DDD --- Build " +  module_name + "-" + module_version + " - Kernel: " + kernel)
        dkms_build_command = ["dkms", "build",
                            "-m", module_name,
                            "-v", module_version,
                            "--dkmstree", get_fake_dkms_root_folder(),
                            "-k", kernel  ]

        if not lib_symlink_exists():
            if usr_lib_modules_exists():
                headers_path = "/usr/lib/modules/" + kernel + "/build/"
            elif usr_src_exists():
                headers_path = "/usr/src/linux-headers-" + kernel
            else:
                print("EEE: I cannot be here")
                raise OSError("I shouldn't be here, should have failed before")
            print(f"WWW: Headers cannot be found in /lib, using {headers_path}")
            dkms_build_command.append("--kernelsourcedir")
            dkms_build_command.append(headers_path)

        try:
            subprocess.run(dkms_build_command, check=True, env=my_env)
            relocate_modules(get_manual_dkms_output_folder(),
                                    module_name, module_version,
                                    module.getKernelTargetDirectory(),
                                    kernel, dkms_conf_path)
            print_dkms_build_log(module_name, module_version, kernel)
        except subprocess.CalledProcessError as e:
            if e.returncode == 77:
                print("WARNING: -------------------------------------------------")
                print("WARNING: -------------------------------------------------")
                print("WARNING: DKMS reported SKIP for ")
                print(f"WARNING: {module_name} for {kernel}")
                print("WARNING: nothing to build for this kernel probably")
                print("WARNING: -------------------------------------------------")
            else:
                print("EEE ------------------------------------------------------")
                print("EEE -------------------ERROR------------------------------")
                print("EEE ------------------------------------------------------")
                print("EEE Couldn't build " + module_name + " for " + kernel)
                print("EEE STOPPING THE BUILD PROCESS")
                print("EEE ------------------------------------------------------")
                print("EEE ------------------------------------------------------")
                print("EEE ----------------BUILD LOG-----------------------------")
                print_dkms_build_log(module_name, module_version, kernel)
                print("EEE ------------------------------------------------------")
                print("EEE ----------------END BUILD LOG-------------------------")
                return False
    return True


def build_dkms_module(module):
    result = download_module(module)
    if not result:
        return False

    result = extract_debian_package(module)
    if not result:
        return False

    result = add_dkms_to_fakeroot(module)
    if not result:
        return False

    result = build_dkms_in_fakeroot(module)
    if not result:
        return False

    return True


def build_manual_modules_for_arch(architecture: str):
    os.makedirs(get_fake_dkms_root_folder(), exist_ok=True)
    os.makedirs(get_manual_dkms_build_folder(), exist_ok=True)
    os.makedirs(get_manual_dkms_output_folder(), exist_ok=True)
    modules = dkms_modules()
    modules.parse_dkms_version_file()
    modules.filter_per_architecture(architecture)
    modules.filter_per_off_series()
    for module in modules.items:
        print("DDD - Building " +  module.modulename)
        result = build_dkms_module(module)
        if not result:
            return False
    return True


########### MAIN CALL ####################
(arg_architecture) = sys.argv[1:][0]
print("build-manual-packages: Called with arg_architecture=" + arg_architecture)
if not build_manual_modules_for_arch(arg_architecture):
    print("EEE - Something went wrong, please check the logs...")
    sys.exit(2)
