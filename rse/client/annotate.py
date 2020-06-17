"""

Copyright (C) 2020 Vanessa Sochat.

This Source Code Form is subject to the terms of the
Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""

from rse.main import Encyclopedia


def main(args, extra):

    # Create a research software encyclopedia
    enc = Encyclopedia(config_file=args.config_file)

    # The type is either criteria or taxonomy
    enc.annotate(
        username=args.username,
        atype=args.type[0],
        unseen_only=not args.all_repos,
        repo=args.repo,
        save=True,
    )
