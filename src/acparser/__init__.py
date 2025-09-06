"Ansible collection parser for developers."

__version__ = "0.3.1"

import sys
import tarfile
import tempfile
import os
import yaml
from identify import identify
import requirements
import subprocess
import warnings
import argparse
from typing import List, Tuple, Optional
import json
import packaging
from pprint import pprint
import re

PACKAGE_INFO = re.compile(
    r"^(?P<namespace>\w+)-(?P<name>\w+)-(?P<version>[0-9a-zA-Z.+-]+)\.tar\.gz$"
)


warnings.filterwarnings("ignore", category=DeprecationWarning)


def extract_tar(filename, output_dir):
    """
    Extracts the given tarball to the output directory.

    :arg filename: tar filename
    :arg output_dir: Directory to extract the tarfile

    :return: None
    """

    tar = tarfile.open(filename)
    tar.extractall(output_dir)


def system(cmd):
    ret = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
    )
    out, err = ret.communicate()
    return out, err, ret.returncode


def process_collection(
    namespace, collection_name, collection_version, tarfilename, check_galaxy=False
):
    """Returns the dictionary containing various metadata of the collection."""

    # Variable to store output from collection
    result = {}

    if check_galaxy:
        result["exists_galaxy"] = False
    result["ansiblecore"] = ""
    result["license"] = ""
    result["license_filename"] = ""
    result["changelog_exists"] = ""
    result["requirement_exists"] = []
    result["community_collections"] = ""

    # checking if the collection exists in galaxy
    if check_galaxy:
        with tempfile.TemporaryDirectory() as collection_dir:
            cmd = f"ansible-galaxy collection download -n -p {collection_dir} {namespace}.{collection_name}:{collection_version}"
            _, _, retcode = system(cmd)
            if retcode == 0:
                downloaded_tarfilename = os.path.join(
                    collection_dir,
                    f"{namespace}-{collection_name}-{collection_version}.tar.gz",
                )
                if os.path.exists(downloaded_tarfilename):
                    result["exists_galaxy"] = True

    # Extract the tar

    with tempfile.TemporaryDirectory() as tmpdirname:
        extract_tar(tarfilename, tmpdirname)

        # check runtime ansible version

        runtime_yml = f"/{tmpdirname}/meta/runtime.yml"
        if os.path.exists(runtime_yml):
            with open(runtime_yml, "r") as fobj:
                data = yaml.load(fobj, Loader=yaml.SafeLoader)
                result["ansiblecore"] = data["requires_ansible"]
        else:
            result["ansiblecore"] = False

        # check collection license
        result["license"], result["license_filename"] = find_license(tmpdirname)

        # check changelog entries
        result["changelog_exists"] = changelog_entries(tmpdirname, collection_version)

        # check reuirements file (find Python dependencies (if any))
        try:
            result["requirement_exists"] = check_requirements(tmpdirname)
        except packaging.requirements.InvalidRequirement as e:
            result["requirements_error"] = str(e)

        # find if any "community" collection is mentioned or not
        result["community_collections"] = check_community_collection(tmpdirname)

        # find "bindep.txt" if any

    return result


def main():
    "Entry point"
    parser = argparse.ArgumentParser()
    parser.add_argument("--tarfile", help="Path to the source tarball", required=True)
    args = parser.parse_args()
    match = PACKAGE_INFO.match(os.path.basename(args.tarfile))
    namespace, collection_name, collection_version = match.groups()

    result = process_collection(
        namespace, collection_name, collection_version, args.tarfile
    )

    if "exists_galaxy" in result:
        if result["exists_galaxy"]:
            print("Source exists in galaxy.")
        else:
            print("Source does not exist in galaxy.")

    if result["ansiblecore"]:
        print(f"\n✅ `requires_ansible` {result['ansiblecore']}")
    else:
        print("❌ `requires_ansible` does not exists.")

    if result["license"]:
        print(f"✅ License found in {result['license_filename']}: {result['license']}")
    else:
        print("❌ `License` does not exists.")
    if result["requirement_exists"]:
        clean_requirement = True

        for data in result["requirement_exists"]:
            for value in data[1]:
                if "<" in value[0] or value[0] == "==":
                    print(
                        f"❌ Requirement with upper boundary {data[0]} {value[0]} {value[1]}"
                    )
                    clean_requirement = False
        if clean_requirement:
            print("✅ Requirements are without upper boundary.")
    else:
        print("✅ No requirements found.")
    if result["changelog_exists"]:
        print("✅ Found Changelog entry.")
    else:
        print("❌ Changelog entry NOT found.")

    if result["community_collections"]:
        print("⚠️ Possible community collection usage found in the following lines.\n")
        print(result["community_collections"])
    else:
        print("✅ No community collection usage found.")


def find_license(source_dir) -> str:
    """
    It prints the guessed license from the license file.

    """
    license = ""
    license_filename = ""
    license_files = ["license", "license.rst", "license.md", "license.txt", "copying"]
    files = os.listdir(source_dir)
    for file in files:
        filename = file.lower()
        if filename in license_files:
            license = identify.license_id(os.path.join(source_dir, file))
            license_filename = file
            break
    return license, license_filename


def changelog_entries(source_dir, collection_version) -> str:
    changelog_files = ["changelog", "changelog.rst", "changelog.md", "changelog.txt"]
    files = os.listdir(source_dir)
    data = ""
    for file in files:
        filename = file.lower()
        if filename in changelog_files:
            changelog = os.path.join(source_dir, file)
            with open(changelog, "r") as fobj:
                data = fobj.read()
                break
    # now we have the changelog in data

    lines = data.split("\n")
    n = 0
    text = []
    for line in lines:
        if line.find(collection_version) != -1:
            n = n + 1
        if n != 0:
            text.append(line)
            n = n + 1
            if n > 10:
                break
    return "\n".join(text)


def check_requirements(source_dir) -> List[Tuple[str, List[str]]]:
    result = []
    requirement_file = os.path.join(source_dir, "requirements.txt")
    if os.path.exists(requirement_file):
        with open(requirement_file, "r") as fobj:
            for req in requirements.parse(fobj):
                result.append((req.name, req.specs))
    return result


def check_community_collection(source_dir) -> str:
    output, error, return_code = system(
        f'grep -rHnF "community." --include="*.y*l" {source_dir}'
    )
    if return_code != 0:
        return ""
    else:
        result = []
        for line in output.decode("utf-8").split("\n"):
            line2 = line.lower()
            if line2.find("changelog.yml") == -1 and line2.find("changelog.yaml") == -1:
                result.append(line)
        return "\n".join(result)


if __name__ == "__main__":
    main()
