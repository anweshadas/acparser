"ansible collection parser"

__version__ = "0.1.0"

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

warnings.filterwarnings("ignore", category=DeprecationWarning)


def export_tar(filename, output_dir):
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


def main():
    "Entry point"
    parser = argparse.ArgumentParser()
    parser.add_argument("--tarfile", help="Path to the source tarball", required=True)
    parser.add_argument(
        "--namespace", help="Namespace of the collection", required=True
    )
    parser.add_argument("--name", help="Name of the collection", required=True)
    parser.add_argument("--version", help="Version of the collection", required=True)
    args = parser.parse_args()
    namespace = args.namespace
    collection_name = args.name
    collection_version = args.version


    EXISTS_GALAXY = False
    REQUIRES_ANSIBLE = ""
    LICENSE = ""
    CHANGELOG = ""
    REQUIREMENTS = []
    COMMUNITY_COLLECTIONS = ""


    with tempfile.TemporaryDirectory() as collection_dir:
        _, _, retcode = system(
            f"ansible-galaxy collection download -n -p {collection_dir} {namespace}.{collection_name}:{collection_version}"
        )
        # check the return code
        if retcode == 0:
            tarfilename = os.path.join(
                collection_dir,
                f"{namespace}-{collection_name}-{collection_version}.tar.gz",
            )
            if os.path.exists(tarfilename):
                EXISTS_GALAXY = True

    # printing the output
    if EXISTS_GALAXY:
        print("Source exists in galaxy.")
    else:
        print("Source does not exist in galaxy.")

    tarfilename = args.tarfile

    with tempfile.TemporaryDirectory() as tmpdirname:
        # Extract the tarball
        export_tar(tarfilename, tmpdirname)

        # check runtime ansible version
        runtime_yml = f"/{tmpdirname}/meta/runtime.yml"
        if os.path.exists(runtime_yml):
            with open(runtime_yml, "r") as fobj:
                data = yaml.load(fobj, Loader=yaml.SafeLoader)
                REQUIRES_ANSIBLE = data['requires_ansible']
                print(
                    f"{namespace}.{collection_name}:{collection_version} requires ansible-core version {data['requires_ansible']}"
                )
        else:
            print("runtime.yml does not exists")

        print("")

        # check collection license
        LICENSE = find_license(tmpdirname)
        print("")

        # check changelog entries
        CHANGELOG = changelog_entries(tmpdirname, collection_version)


        # check reuirements file (find Python dependencies (if any))
        REQUIREMENTS = check_reuirements(tmpdirname)
        print("")

        # find if any "community" collection is mentioned or not
        COMMUNITY_COLLECTIONS = check_community_collection(tmpdirname)

        # find "bindep.txt" if any


def find_license(source_dir) -> str:
    """
    It prints the guessed license from the license file.

    """
    license_files = ["license", "license.rst", "license.md", "license.txt", "copying"]
    files = os.listdir(source_dir)
    for file in files:
        filename = file.lower()
        if filename in license_files:
            license = identify.license_id(os.path.join(source_dir, file))
            print(f"The license as mentioned in the {file} file is {license}")
            return license
    return ""


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


def check_reuirements(source_dir) -> List[Tuple[str,List[str]]]:
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
