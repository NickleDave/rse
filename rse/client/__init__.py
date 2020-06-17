#!/usr/bin/env python

"""

Copyright (C) 2020 Vanessa Sochat.

This Source Code Form is subject to the terms of the
Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""

from rse.logger import RSE_LOG_LEVEL, RSE_LOG_LEVELS
from rse.defaults import RSE_CONFIG_FILE
import rse
import argparse
import sys
import logging


def get_parser():
    parser = argparse.ArgumentParser(
        description="Research software engineering software inspector."
    )

    parser.add_argument(
        "--version",
        dest="version",
        help="suppress additional output.",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--log_level",
        dest="log_level",
        choices=RSE_LOG_LEVELS,
        default=RSE_LOG_LEVEL,
        help="Customize logging level for rse inspector.",
    )

    # Configuration file
    parser.add_argument(
        "--config_file",
        dest="config_file",
        default=RSE_CONFIG_FILE,
        help="Path to rse.ini configuration file.",
    )

    description = "actions for rse"
    subparsers = parser.add_subparsers(
        help="rse actions", title="actions", description=description, dest="command",
    )

    # print version and exit
    subparsers.add_parser("version", help="show software version")

    # Annotate criteria or taxonomy
    annotate = subparsers.add_parser(
        "annotate", help="Annotate a database with criteria or taxonomy"
    )
    annotate.add_argument(
        "type",
        help="Type to annotate (taxonomy or criteria)",
        nargs=1,
        choices=["taxonomy", "criteria"],
    )
    annotate.add_argument(
        "-u",
        "--username",
        dest="username",
        default=None,
        help="GitHub username (must be provided if not available with git config)",
    )
    annotate.add_argument(
        "-r",
        "--repo",
        dest="repo",
        default=None,
        help="Specify a particular repository name to annotate.",
    )
    annotate.add_argument(
        "--all",
        "-a",
        dest="all_repos",
        help="Annotate all repos, even those that have already been seen (defaults to show only those unseen).",
        default=False,
        action="store_true",
    )

    # Generate a key for the interface
    generate = subparsers.add_parser(
        "generate-key",
        help="generate a key for rse start, should be exported to RSE_SERVER_KEY.",
    )

    # Init
    init = subparsers.add_parser(
        "init", help="Add an rse.ini to the present working directory."
    )
    init.add_argument(
        "path", help="Path to generate rse.ini file", nargs="?", default=".",
    )

    # Config
    config = subparsers.add_parser(
        "config", help="Update an rse.ini configuration file."
    )

    # Clear
    clear = subparsers.add_parser("clear", help="Remove software from the database.")
    clear.add_argument("target", nargs="?")
    clear.add_argument(
        "--force",
        dest="force",
        help="Don't ask for confirmation for delete (for headless).",
        default=False,
        action="store_true",
    )

    # Exists
    exists = subparsers.add_parser(
        "exists", help="Determine if an entry exists in the database."
    )

    # Exists
    export = subparsers.add_parser(
        "export", help="Export repository names, metadata, or static files."
    )
    export.add_argument(
        "--force",
        dest="force",
        help="Don't ask for confirmation to overwrite existing file(s).",
        default=False,
        action="store_true",
    )
    export.add_argument(
        "path",
        help="Fileame to export repos to (default repos.txt)",
        default="repos.txt",
    )

    # Update
    update = subparsers.add_parser(
        "update", help="Update one or more software entries."
    )

    # Specify a database, if not sqlite must include a complete string
    update.add_argument(
        "-p",
        "--path",
        dest="path",
        default=None,
        help="Path to single folder or set of folders to update.",
    )
    update.add_argument(
        "--force",
        dest="force",
        help="If a repository is not present, add it.",
        default=False,
        action="store_true",
    )

    # List repos and print to terminal
    ls = subparsers.add_parser("ls", help="List software")
    ls.add_argument(
        "parser", help="list one or more parsers or specific software.", nargs="*"
    )

    # Search for software
    search = subparsers.add_parser(
        "search", help="Search for a piece of research software",
    )
    search.add_argument("query", nargs="*")

    # Shell
    subparsers.add_parser(
        "shell", help="start an interactive shell for an encyclopedia"
    )

    # Start the rse dashboard
    start = subparsers.add_parser(
        "start", help="start an interface to browse software (requires Flask)"
    )
    start.add_argument(
        "--port",
        dest="port",
        default=5000,
        type=int,
        help="select port to run dashboard on (defaults to 5000)",
    )
    start.add_argument(
        "--host",
        dest="host",
        default="127.0.0.1",
        type=str,
        help="the hostname to run for the server (defaults to 127.0.0.1)",
    )

    start.add_argument(
        "--debug",
        dest="debug",
        help="run server in debug mode (defaults to False)",
        default=False,
        action="store_true",
    )

    # Print complete metadata for a specific piece of software
    get = subparsers.add_parser("get", help="Show metadata for software")
    add = subparsers.add_parser("add", help="Add a repository to the database.")

    for command in [exists, config, init]:
        command.add_argument(
            "--database",
            dest="database",
            choices=["filesystem", "sqlite"],
            default=None,
            help="database backend to use, to override configuration.",
        )

    for command in [exists, get]:
        command.add_argument("uid", help="uri within software namespace.", nargs="?")

    for command in [update, add]:
        command.add_argument("uid", help="uri within software namespace.", nargs="?")
        command.add_argument(
            "--file",
            dest="file",
            default=None,
            help="single line delimited file of repositories.",
        )

    return parser


def main():
    """main entrypoint for rse
    """

    parser = get_parser()

    def help(return_code=0):
        """print help, including the software version and active client 
           and exit with return code.
        """
        version = rse.__version__

        print("\nResearch Software Engineering software inspector v%s" % version)
        parser.print_help()
        sys.exit(return_code)

    # If the user didn't provide any arguments, show the full help
    if len(sys.argv) == 1:
        help()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, extra = parser.parse_known_args()

    # Set the logging level
    logging.basicConfig(level=getattr(logging, args.log_level))
    bot = logging.getLogger("rse.client")
    bot.setLevel(getattr(logging, args.log_level))

    # Show the version and exit
    if args.command == "version" or args.version:
        print(rse.__version__)
        sys.exit(0)

    # Does the user want a shell?
    if args.command == "annotate":
        from .annotate import main
    if args.command == "add":
        from .add import main
    if args.command == "clear":
        from .clear import main
    if args.command == "config":
        from .config import main
    if args.command == "exists":
        from .exists import main
    if args.command == "export":
        from .export import main
    if args.command == "generate-key":
        from .generate import main
    if args.command == "update":
        from .update import main
    if args.command == "get":
        from .get import main
    if args.command == "init":
        from .init import main
    if args.command == "ls":
        from .listing import main
    if args.command == "search":
        from .search import main
    if args.command == "shell":
        from .shell import main
    if args.command == "start":
        from .start import main

    # Pass on to the correct parser
    return_code = 0
    # try:
    main(args=args, extra=extra)
    sys.exit(return_code)
    # except UnboundLocalError:
    #    return_code = 1

    help(return_code)


if __name__ == "__main__":
    main()
