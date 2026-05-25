#!/bin/bash

set -euo pipefail

BUILDARCH="${1:-amd64}"
CHROOT="${2:-}"

# Standard way of binary building a package.
function runbuildNewPackage()
{
  folder=$1
  echo "->>>>>>>>>>>>>>> $folder"
  pushd $folder
  echo "==============================  ${folder} ======================="
  fakeroot debian/rules clean
  dpkg-buildpackage -b -a${BUILDARCH} -d --no-sign
  echo "================================================================="
  echo ""
  echo ""
  popd
}

# Generate a list of expected header .deb filenames for a given architecture,
# based on debian/changelog (for version/ABI) and debian/package.config
# (for per-flavour arch mappings). Populates the global EXPECTED_HEADERS array.
function listExpectedHeaders()
{
  local arch="${1}"
  local changelog="linux-lmm/debian/changelog"
  local pkg_config="linux-lmm/debian/package.config"

  local version abi
  version=$(dpkg-parsechangelog -l"${changelog}" -SVersion)
  abi=$(echo "${version}" | sed -ne 's/\([0-9]*\.[0-9]*\.[0-9]*\-[0-9]*\)\..*/\1/p')
	version="${version%+*}"

	EXPECTED_HEADERS=()

  # The arch-independent common headers
  EXPECTED_HEADERS+=("linux-headers-${abi}_${version}_all.deb")

  # Per-flavour arch-specific headers from package.config
  while read -r verb flavour archs; do
    [[ "${verb}" == "build" ]] || continue
    for a in ${archs}; do
      if [[ "${a}" == "${arch}" ]]; then
        EXPECTED_HEADERS+=("linux-headers-${abi}-${flavour}_${version}_${arch}.deb")
        break
      fi
    done
  done < "${pkg_config}"
}

# Check that all files in the EXPECTED_HEADERS array are present in the
# given search directory. Exits if headers are missing.
function checkExpectedHeaders()
{
  local search_dir="${1}"
  local missing=0

  for deb in "${EXPECTED_HEADERS[@]}"; do
    if [[ ! -f "${search_dir}/${deb}" ]]; then
      echo "WARNING: Expected header not found: ${search_dir}/${deb}" >&2
      missing=1
    fi
  done

  if [[ "${missing}" -eq 0 ]]; then
    echo "All expected headers found in ${search_dir}"
  else
    echo "Some expected headers are missing; bailing"
    exit 1
  fi
}

# Export pre-generated signing keys, useful for multiple runs with the same MOK
#  key to avoid having to enroll a new key every time.
function exportSigningKey()
{
  local PRIV_KEY="./private_key.priv"
  local PUB_KEY="./public_key.der"

  cat << 'EOF' > "${PRIV_KEY}"
-----BEGIN PRIVATE KEY-----
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
9LLfLNc2hJKGHNTFw3XSQxguDw+mUA==
-----END PRIVATE KEY-----
EOF

  cat << 'EOF' | base64 -d > "${PUB_KEY}"
MIIFZzCCA0+gAwIBAgIUbIW9vpjJLYiQWGSuGvNe/apZ/N0wDQYJKoZIhvcNAQELBQAwQzEiMCAGA1UECgwZQ2Fub25pY2FsIENCRCBUZXN0IFNlcnZlcjEdMBsGA1UEAwwUQ0JEIFRlc3QgU2lnbmluZyBrZXkwIBcNMjYwNTE5MDgwNDQ4WhgPMjEyNjA0MjUwODA0NDhaMEMxIjAgBgNVBAoMGUNhbm9uaWNhbCBDQkQgVGVzdCBTZXJ2ZXIxHTAbBgNVBAMMFENCRCBUZXN0IFNpZ25pbmcga2V5MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA2MW82cIKIAnyBymAFx4AdiCVqusndpufkt/tS/tL7BqIELe8pCn3B1x+xPFpxjmA47tVQhIZRbU3WSLuyy+JU/Po0MWx7pwTIiW070Pjs7ftluepsUuSaHwtbbDqEN0VKlzSgCD7xr7sFnQXrcw2eCeGtRpUpBLIl7TSgQ/VHcGhO9VwP1W60QJQtKO2MD/JMFM+1WV2JWsxPgKRvDlKU8htQyKuIkKoAvwknMuV4XeSz2N5UQ6I+8AtDbbReHg3fLklcIFNVqSp8f4rWm2xx3NJMEWcihRnWMwy2+FZu/gSd4EGK8VLAXjctC/HM6DC6FE1Dv4LXZBrZWH+Y8gxPjPnegF+HTqPKlCx8ktYLSg1+L4p8YDMLwZcpiYyaWmW2lxkz+L5xzsKBGhMt/duWeUCucnqPIFYEXPh1IKbG6DwNObJm9Y5reArbPhUDJCNNYbdaRRo8aJ82A3KuUKhjfBhP9v1z5L5/1EeBPff5wxedxJIYRio1OcmfHl6aqc4kp/+VHGHE/z1kuJlhg+Y1RGrg8zb3iHfK+A98pVWFxM1XYU3i3QIPoPeB6qC50s0BkHVUf/jVKyZIY8SigzAMpm6ZxL46+Duaay2GA6ROg11NUeuK6PSMwefVtrPpF9+yuZ0FjRIkgU/tLmXGlJTEakh0Ue7XIczmcMNKVZdhRkCAwEAAaNRME8wDAYDVR0TAQH/BAIwADALBgNVHQ8EBAMCB4AwHQYDVR0OBBYEFIr2QTyZOpToG+mZGZCSnJoLumdpMBMGA1UdJQQMMAoGCCsGAQUFBwMDMA0GCSqGSIb3DQEBCwUAA4ICAQDAKHd+RqFHydexWo32XWV43acxx1jb7rPMTW4HHzgixPRpvg+ADaYaBaAFfvRcqpVi0XR6XWFGswaZnmH3QWYBKsC3uGzkKWWING/wXySNGfAzOA3WkKQPpM3UTY9RZLg4wsT36jIvdVNfJAc9ryiKT28/lPFNU/Z06/8xGRf0h67rq/tqS6m3q+fflzgTCUG8of061aWCnUDPqlzddfpq/276Xhfnv6ebdcEvkFnfjexOwNepBGoGdFVqbZh8/zPYuAcJUyiQg9l2TwiXaMeWo923TQNLy+ct28vbUBsL09c94Hqy/+H9iKsXYBrUo/U3QC8e0QU2CKDBPcdtTVwTosGjr9hCPuOJ5S/OSxxXXvpk3fq3+0SPO+w+XNjeKT1yCd8j+bQvTZzJGObp0ryZiPrle7ne20QycIQfciqrNa5by/bXLhckyfPoU0w8zKwCrP4MHkBgJ69FD2vQ/LNcqSrYR5mKz3iA3f62AlRUJNyHICK0o38Q6jlQMK+xwIN4yewN+mHUFqZMrBMbZbl4v3jqdwCzghgD2JjATd/gAuquZeIwnMfz6q0fqXar7RLyrNRT6OFirjLMng4WEpRQXbRFslfyfEFp5yTWlLRHqfPwwxX2lzmo20oa4eTXyTKIbGxyomdRcDmSJvRg5tMy7aNndogSDyhbitfJ0quFkQ==
EOF
}

# How to generate a random signing key, in case we need to regenerate a new one.
function generateRandomSigningKey()
{
  local CONFIG_FILE="x509.genkey"

  echo "Creating OpenSSL configuration..."
  cat << 'EOF' > "$CONFIG_FILE"
[ req ]
default_bits = 4096
distinguished_name = req_distinguished_name
prompt = no
string_mask = utf8only
x509_extensions = my_extensions

[ req_distinguished_name ]
O  = Canonical CBD Test Server
CN = CBD Test Signing key

[ my_extensions ]
basicConstraints=critical,CA:FALSE
keyUsage=digitalSignature
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid
extendedKeyUsage=codeSigning
EOF

  echo "Generating keys..."
  openssl req -x509 -new -nodes -utf8 -sha256 -days 36500 \
    -batch -config "$CONFIG_FILE" \
    -outform DER -out public_key.der \
    -keyout private_key.priv

  rm "$CONFIG_FILE"
  echo "Keys generated: public_key.der and private_key.priv"
}

# Sign the .ko files in the latest tarball and create a new signed tarball.
function signTarball()
{
  local PRIV_KEY="./private_key.priv"
  local PUB_KEY="./public_key.der"
  local SOURCE_DIR="/opt/linux-main-modules"
  local OUTPUT_NAME="signed.tar.gz"

  if [[ ! -f "$PRIV_KEY" || ! -f "$PUB_KEY" ]]; then
      echo "Error: Keys not found in current directory."
      return 1
  fi

  local SRC_FILE=$(ls -t ${SOURCE_DIR}/linux-main-modules_*.tar.gz 2>/dev/null | head -n 1)

  if [[ -z "$SRC_FILE" ]]; then
      echo "Error: No tarball found in $SOURCE_DIR"
      return 1
  fi

  echo "Processing: $SRC_FILE"

  local TEMP_DIR=$(mktemp -d)
  echo "Using temp workspace: $TEMP_DIR"

  tar -xzf "$SRC_FILE" -C "$TEMP_DIR"

  echo "Generating detached signatures..."
  find "$TEMP_DIR" -type f -name "*.ko" | while read -r ko_file; do
    echo "  Signing: $(basename "$ko_file")"

    openssl cms -sign -in "$ko_file" -inkey "$PRIV_KEY" \
                -signer "$PUB_KEY" -outform DER \
                -noattr -md sha256 -out "${ko_file}.sig"
    sig_size=$(stat -c %s "${ko_file}.sig")
    printf "\x00\x00\x02\x00\x00\x00\x00\x00" > footer.bin
    printf "%08x" "${sig_size}" | xxd -r -p >> footer.bin
    printf "~Module signature appended~\n" >> footer.bin
    cat footer.bin >> "${ko_file}.sig"
    rm footer.bin
  done

  echo "Creating final tarball: $OUTPUT_NAME"
  tar -czf "$(pwd)/$OUTPUT_NAME" -C "$TEMP_DIR" .

  rm -rf "$TEMP_DIR"
  echo "Signed tarball created in $(pwd)/$OUTPUT_NAME"

  mkdir SIGNED || true
  mv "$OUTPUT_NAME" SIGNED/
}

function exportCrossSymbols()
{
  export native_arch=$(dpkg --print-architecture)
  CROSS_BIN=""
  CROSS_GCC="";
  CROSS_NAME="";
  if [ "$BUILDARCH" != "$native_arch" ]; then
    case "$BUILDARCH" in
      arm64)   CROSS_PREFIX="aarch64-linux-gnu";     CROSS_NAME="arm64";   CROSS_BIN="aarch64" ;;
      armhf)   CROSS_PREFIX="arm-linux-gnueabihf";   CROSS_NAME="arm";     CROSS_BIN="arm" ;;
      ppc64el) CROSS_PREFIX="powerpc64le-linux-gnu"; CROSS_NAME="powerpc"; CROSS_BIN="powerpc64le" ;;
      s390x)   CROSS_PREFIX="s390x-linux-gnu" ;      CROSS_NAME="s390x";   CROSS_BIN="s390x" ;;
      riscv64) CROSS_PREFIX="riscv64-linux-gnu";     CROSS_NAME="riscv";   CROSS_BIN="riscv64" ;;
      *)       CROSS_PREFIX="";;
    esac
    if [ -n "$CROSS_PREFIX" ]; then
      export CROSS_GCC="gcc-${CROSS_PREFIX}"
      export LMM_BUILD_ARCH="$BUILDARCH"
      export LMM_CROSS_BIN="$CROSS_BIN"
      export LMM_CROSS_GCC="$CROSS_GCC"
      export LMM_CROSS_NAME="$CROSS_NAME"
      export LMM_CROSS_PREFIX="$CROSS_PREFIX"
      export QEMU_LD_PREFIX=/usr/${CROSS_BIN}-linux-gnu
    fi
  fi
}

function setupSchroot()
{
if [ -n "$CHROOT" ]; then
    schroot_session=$(schroot -b -c "$CHROOT")
    trap 'schroot -e -c "$schroot_session" || true' EXIT

    sudo schroot -u root -r -c "$schroot_session" -d "$(pwd)" -- bash <<EOF
        set -e
        if [ "$BUILDARCH" != "$native_arch" ]; then
            source /etc/lsb-release
            sed -i "s|deb http|deb [arch=$native_arch] http|g" /etc/apt/sources.list
            echo "deb [arch=$BUILDARCH] http://ports.ubuntu.com/ubuntu-ports \${DISTRIB_CODENAME} main universe restricted multiverse" > /etc/apt/sources.list.d/cross.list
            echo "deb [arch=$BUILDARCH] http://ports.ubuntu.com/ubuntu-ports \${DISTRIB_CODENAME}-updates main universe restricted multiverse" >> /etc/apt/sources.list.d/cross.list
            dpkg --add-architecture $BUILDARCH
        fi
        rm -rf /var/lib/apt/lists/*
        apt-get -y update
        apt install -y python3 fakeroot debhelper openssl xxd
        (cd ./linux-lmm && fakeroot debian/rules clean)
        apt-get -y -q=1 build-dep ./linux-lmm
        if [ "$BUILDARCH" != "$native_arch" ]; then
            if [ -n "$CROSS_GCC" ]; then
                apt-get -y install gcc "$CROSS_GCC" libc6-dev-"$BUILDARCH"-cross qemu-user
                dpkg --add-architecture $BUILDARCH
                apt-get -y install libdw1:$BUILDARCH libelf1:$BUILDARCH libssl3:$BUILDARCH zlib1g:$BUILDARCH
            fi
        fi
        for deb in ${HEADERS_TO_INSTALL}; do
            dpkg -i --force-architecture --force-depends "\$deb"
        done
        if [ "$BUILDARCH" != "$native_arch" ]; then
            # I think we need this because in resolute the qemu name has changed, meh
            ln -s /usr/bin/qemu-${CROSS_BIN} /usr/bin/qemu-${CROSS_BIN}-static
            # This seems to not be needed, but threads said it should be.
            #ln -s /usr/aarch64-linux-gnu/lib/ld-linux-aarch64.so.1 /lib/ld-linux-aarch64.so.1

            # This part is quite interesting. So, it looks like the deb packaging
            # of the headers when cross compiling is quite broken, so we need to
            # manually copy the Makefile back in, or it will be a constant
            # infinite loop of a symlink calling itself
            rm -f /usr/src/linux-headers-${KERNEL_ABI_VERSION}/arch/${CROSS_NAME}/Makefile
            dpkg-deb --fsys-tarfile linux-headers-${KERNEL_ABI_VERSION}_${KERNEL_MAIN_VERSION_CLEAN}_all.deb \
                | tar -xO ./usr/src/linux-headers-${KERNEL_ABI_VERSION}/arch/${CROSS_NAME}/Makefile \
                > /usr/src/linux-headers-${KERNEL_ABI_VERSION}/arch/${CROSS_NAME}/Makefile
        fi
EOF

    sudo schroot -u root -r -c "$schroot_session" -d "$(pwd)" -- bash "$(realpath "$0")" "$BUILDARCH"
    exit $?
fi

}

# ================= MAIN ========================
export LOCAL_SIGNED_LMM_DKMS_PATH=$(pwd)/SIGNED

SUDO=""
if [ "$EUID" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "Error: This step requires root privileges" >&2
    exit 1
  fi
fi

if [ ! -d "linux-lmm" ]; then
  echo "ERROR: linux-lmm directory not found. Please run the script from the correct location."
  exit 1
fi

# Grep the version we are working with
pushd linux-lmm
VERSION=$(dpkg-parsechangelog -ldebian/changelog -SVersion)
KERNEL_ABI_VERSION=$(echo "${VERSION}" | sed -ne 's/\([0-9]*\.[0-9]*\.[0-9]*\-[0-9]*\)\..*/\1/p')
KERNEL_MAIN_VERSION=$(echo "${VERSION}" | sed -e 's/\+[0-9][0-9]*$$//')
KERNEL_MAIN_VERSION_CLEAN="${KERNEL_MAIN_VERSION%+*}"
KERNEL_META_VERSION=$(echo "${KERNEL_ABI_VERSION}" | sed -e 's/-/./')
popd

listExpectedHeaders "$BUILDARCH"
checkExpectedHeaders "$(pwd)"
HEADERS_TO_INSTALL="${EXPECTED_HEADERS[*]}"

# Export symbols used for cross compiling, in the particular the ones for LMM
exportCrossSymbols

# Setup the schroot environment, if required
setupSchroot

# Cleanup folders for local builds
if [ -d "OUTPUT" ]; then
  rm -rf OUTPUT
fi
mkdir OUTPUT
if [ -d "SIGNED" ]; then
  rm -rf SIGNED
fi

# Build the modules and move artifacts to OUTPUT
runbuildNewPackage linux-lmm
$SUDO dpkg -i --force-architecture linux-main-modules_${KERNEL_MAIN_VERSION}_*.deb
mv linux-main-modules_${KERNEL_MAIN_VERSION}_*.* OUTPUT/

# Build the ancillary to make linux-main-signed happy, move artifacts to OUTPUT
runbuildNewPackage linux-lmm/debian/ancillary/linux-main-generate
mv linux-lmm/debian/ancillary/linux-main-generate_* .
$SUDO dpkg -i --force-architecture linux-main-generate_${KERNEL_MAIN_VERSION}_*.deb
mv linux-main-generate_${KERNEL_MAIN_VERSION}_*.* OUTPUT/

# Sign the modules, we can either generate a random signing key, or use the
#  an embedded one; probably for CBD the latter is a better option.
#generateRandomSigningKey
exportSigningKey
signTarball
runbuildNewPackage linux-lmm/debian/ancillary/linux-main-signed

# Output everything up so CBD can export it as a single artifact
mv linux-lmm/debian/ancillary/linux-main-signed_* OUTPUT/
mv linux-lmm/debian/ancillary/*.deb OUTPUT/
# Output the public key as well, so they can be used to resign or to add to MOK in
#  case secure boot is enabled.
mv public_key.der OUTPUT/
rm private_key.priv
