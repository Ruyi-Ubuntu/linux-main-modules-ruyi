#! /usr/bin/python3

import sys

class variant_helper:
    variants: []

    def sanitise(self, string: str):
        return string.replace("\n","")

    def __init__(self):
        self.variants = []
        with open("debian/variants") as var_f:
            for i, line in enumerate(var_f):
                if i == 0:
                    # Skip the line with the kernel version only
                    continue
                sane_line = self.sanitise(line)
                if sane_line == "--":
                    self.variants.append("")
                else:
                    self.variants.append(sane_line)

def find_variants():
    var = variant_helper()
    return var.variants

#===============================  DEBUG  =======================================
if __name__ == "__main__":
    var = find_variants()
    for v in var:
        print(v)

