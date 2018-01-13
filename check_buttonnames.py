#!/usr/bin/env python

import sys
# if sys.version_info[0] != 3:
#     print("This script requires Python 3.")
#     exit(1)

from os import path
from collections import OrderedDict
import string
import collections
import shutil
import argparse
import csv
import re

FILE_HEADER = """\
# Game Controller Button Name DB
# Source: https://github.com/gabomdq/SDL_GameControllerDB
#
# Help
# Format : guid,name,a,b,hint,leftshoulder,lefttrigger,rightshoulder,\
righttrigger,x,y,platform
#
# Button strings (a,b,x,y) are :
#     A, B, C, T, U, X, Y, Z, CROSS, SQUARE, TRIANGLE, CIRCLE, 1, 2, 3, 4, 5, 6
#
# Trigger strings (leftshoulder,lefttrigger,rightshoulder,righttrigger) are :
#     LB, L1, LT, L2, RB, R1, RT, R2, L, R, ZL, ZR, Z
#
# Hints are :
#     XBOX, PS, NINTENDO, SEGA, ARCADE
#
# Example
# 03000000022000000090000000000000,8Bitdo NES30 Pro,a:B,b:A,hint:NINTENDO,\
leftshoulder:L1,lefttrigger:L2,rightshoulder:R1,righttrigger:R2,x:Y,y:X,\
platform:Windows,
"""

mappings_dict = OrderedDict([
    ("Windows", {}),
    ("Mac OS X", {}),
    ("Linux", {}),
    ("Android", {}),
    ("iOS", {}),
])

parser = argparse.ArgumentParser()
parser.add_argument("input_file", help="database file to check, " \
        "ex. buttonnamedb.txt")
parser.add_argument("--format", help="sorts, formats and removes duplicates",
        action="store_true")
parser.add_argument("--import_controllerdb", metavar="controllerdb",
        help="imports and creates empty mappings from gamecontrollerdb.txt")

class Mapping:
    GUID_REGEX = re.compile(r"^(xinput|[0-9a-fA-F]{32,32})$")
    BUTTON_REGEX = re.compile(r"^(A|B|C|T|U|X|Y|Z|CROSS|SQUARE|TRIANGLE|CIRCLE"\
            "|1|2|3|4|5|6)$")
    HINT_REGEX = re.compile(r"^(XBOX|PS|NINTENDO|SEGA|ARCADE)$")
    BUMPER_REGEX = re.compile(r"^(LB|L1|LT|L2|RB|R1|RT|R2|L|R|ZL|ZR|Z)$")

    KEY_REGEXES = {
        ("a", "b", "x", "y"): BUTTON_REGEX,
        ("hint"): HINT_REGEX,
        ("leftshoulder", "lefttrigger", "rightshoulder", "righttrigger"): \
                BUMPER_REGEX,
    }

    def __init__(self, mapping_string, line_number, clear_buttons = False):
        self.guid = ""
        self.name = ""
        self.platform = ""
        self.line_number = 0
        self.__keys = {
            "a": "",
            "b": "",
            "hint": "",
            "leftshoulder": "",
            "lefttrigger": "",
            "rightshoulder": "",
            "righttrigger": "",
            "x": "",
            "y": "",
        }

        self.line_number = line_number
        reader = csv.reader([mapping_string], skipinitialspace=True)
        mapping = next(reader)
        mapping = list(filter(None, mapping))
        self.set_guid(mapping[0])
        mapping.pop(0)
        self.set_name(mapping[0])
        mapping.pop(0)
        self.set_platform(mapping)
        self.set_keys(mapping, clear_buttons)

        # Remove empty mappings.
        self.__keys = {k:v for (k,v) in self.__keys.items() if v is not ""}

        if clear_buttons:
            self.__keys["hint"] = "remove"
            for k in self.__keys:
                if self.__keys[k] == "remove":
                    self.__keys[k] = ""

        if "hint" not in self.__keys:
            raise ValueError("Hint is required.")



    def set_guid(self, guid):
        if not self.GUID_REGEX.match(guid):
            raise ValueError("GUID malformed.", guid)

        self.guid = guid


    def set_name(self, name):
        name = re.sub(r" +", " ", name)
        self.name = name


    def set_platform(self, mapping):
        platform_kv = next((x for x in mapping if "platform:" in x), None)
        if platform_kv == None:
            raise ValueError("Required 'platform' field not found.")

        platform = platform_kv.split(':')[1]
        if platform not in mappings_dict.keys():
            raise ValueError("Invalid platform.", platform)

        self.platform = platform
        index = mapping.index(platform_kv)
        mapping.pop(index)


    def get_key_count(self):
        return len(self.__keys)


    def set_keys(self, mapping, clear_buttons):
        throw = False
        error_msg = ""

        for kv in mapping:
            button_key, button_val = kv.split(':')

            if clear_buttons:
                if button_key in self.__keys:
                    self.__keys[button_key] = "remove"
                continue

            if not button_key in self.__keys:
                raise ValueError("Unrecognized key.", button_key)

            # Gather duplicates.
            if self.__keys[button_key] is not "":
                throw = True
                error_msg += "%s (was %s:%s), " \
                        % (kv, button_key, self.__keys[button_key])
                continue

            for butt,regex in self.KEY_REGEXES.items():
                if not button_key in butt:
                    continue

                if not regex.match(button_val):
                    raise ValueError("Invalid value.", button_key, button_val)

                self.__keys[button_key] = button_val
                break

        if throw:
            raise ValueError("Duplicate keys detected.", error_msg)

    def __str__(self):
        ret = "Mapping {\n  guid: %s\n  name: %s\n  platform: %s\n" \
            % (self.guid, self.name, self.platform)

        ret += "  Keys {\n"
        for key,val in self.__keys.items():
            ret += "    %s: %s\n" % (key, val)

        ret += "  }\n}"
        return ret


    def serialize(self):
        ret = "%s,%s," % (self.guid, self.name)
        sorted_keys = sorted(self.__keys.items())
        for key,val in sorted_keys:
            ret += "%s:%s," % (key, val)
        ret += "platform:%s," % (self.platform)
        return ret


def import_controllerdb(filepath, debug_out = False):
    global mappings_dict # { "platform": { "guid": Mapping }}
    input_file = open(filepath, mode="r")

    for lineno, line in enumerate(input_file):
        if line.startswith('#') or line == '\n':
            continue
        try:
            mapping = Mapping(line, lineno + 1, True)
        except ValueError as e:
            print("\nError at line #" + str(lineno + 1))
            print(e.args)
            print("Ignoring mapping")
            print(line)
            continue

        if mapping.guid in mappings_dict[mapping.platform]:
            continue
        if mapping.get_key_count() == 0:
            continue

        if debug_out:
            print("%s : Importing %s" % (mapping.platform, mapping.name))

        mappings_dict[mapping.platform][mapping.guid] = mapping
    input_file.close()


def main():
    global mappings_dict # { "platform": { "guid": Mapping }}
    global parser
    args = parser.parse_args()
    success = True

    # Tests.
    print("\nApplying checks.")

    input_file = open(args.input_file, mode="r")
    for lineno, line in enumerate(input_file):
        if line.startswith('#') or line == '\n':
            continue
        try:
            mapping = Mapping(line, lineno + 1)
        except ValueError as e:
            print("\nError at line #" + str(lineno + 1))
            print(e.args)
            print("In mapping")
            print(line)
            success = False
            continue

        if mapping.guid in mappings_dict[mapping.platform]:
            print("Duplicate detected at line #" + str(lineno + 1))
            prev_mapping = mappings_dict[mapping.platform][mapping.guid]
            print("Previous mapping at line #" + str(prev_mapping.line_number))
            print("In mapping")
            print(line)
            success = False
            continue

        mappings_dict[mapping.platform][mapping.guid] = mapping
    input_file.close()

    if success:
        print("No mapping errors found.")
    else:
        sys.exit(1)


    # Misc tools.

    if args.import_controllerdb is not None:
        print("Importing mappings from gamecontrollerdb.txt.")
        if not args.format:
            print("Use --format option to save database. Running in debug "\
                    "output mode...")
        import_controllerdb(args.import_controllerdb, not args.format)

    if args.format:
        print("\nFormatting db.")
        out_filename = path.splitext(input_file.name)[0] + "_format.txt"
        out_file = open(out_filename, 'w')
        out_file.write(FILE_HEADER)
        for platform,p_dict in mappings_dict.items():
            out_file.write("\n")
            out_file.write("# " + platform + "\n")
            sorted_p_dict = sorted(p_dict.items(),
                    key=lambda x: x[1].name.lower())

            for guid,mapping in sorted_p_dict:
                out_file.write(mapping.serialize() + "\n")

        out_file.close()
        backup_filename = (path.join(path.split(input_file.name)[0],
                ".bak." + path.split(input_file.name)[1]))
        shutil.copyfile(input_file.name, backup_filename)
        shutil.move(out_filename, input_file.name)


if __name__ == "__main__":
    main()

