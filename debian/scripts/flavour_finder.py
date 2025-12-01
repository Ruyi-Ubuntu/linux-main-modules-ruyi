#! /usr/bin/python3 

import sys
if sys.version_info >= (3, 9):
    List = list
else:
    from typing import List

class flavour_item:
    flavour: str = ""
    archs = []

    def __init__(self, package_config_line: List[str]):
        self.flavour = package_config_line[1]
        self.archs = []
        for item in package_config_line[2:]:
            self.archs.append(item.replace("\n",""))


class flavours:
    items : flavour_item = []

    def __init__(self):
        self.items = []
        with open("debian/package.config", "r") as fp_dpc:
            for line in fp_dpc:
                parms = line.split(" ")
                if parms[0] == "build":
                    item = flavour_item(parms)
                    self.items.append(item)


def find_flavours_from_arch(architecture: str):
    res = []
    flavs = flavours()
    for f in flavs.items:
        if architecture in f.archs:
            res.append(f.flavour)
    return res


def find_flavours():
    flavs = flavours()
    return flavs.items


def find_all_archs():
    archs = []
    flavs = find_flavours()
    for f in flavs:
        for a in f.archs:
            if a not in archs:
                archs.append(a)
    return archs

if __name__ == "__main__":
    res = ""
    archs = find_all_archs()
    for i, a in enumerate(archs):
        res += a
        if i < len(archs) - 1:
            res += " "
    print(res)


# -------------------------------------------------------------------
# for manual testing sake
#if __name__ == "__main__":
#    flavs = find_flavours()
#    for f in flavs:
#        res = f.flavour + " ["
#        for i, a in enumerate(f.archs):
#            res += a
#            if i < len(f.archs) - 1:
#                res += " "
#        res += "]"
#        print(res)

#    print("---------------------")
#    flavs = find_flavours_from_arch("amd64")
#    for f in flavs:
#        print(f)
