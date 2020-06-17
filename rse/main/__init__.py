"""

Copyright (C) 2020 Vanessa Sochat.

This Source Code Form is subject to the terms of the
Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""

from rse.main.config import Config
from rse.defaults import RSE_DATABASE, RSE_PARSERS, RSE_CONFIG_FILE

from rse.exceptions import RepoNotFoundError
from rse.main.database import init_db
from rse.utils.prompt import confirm, choice_prompt
from rse.utils.file import read_file
from rse.utils.command import get_github_username
from rse.main.parsers import get_parser
from rse.main.criteria import get_criteria
from rse.main.taxonomy import get_taxonomy
from rse.logger.message import bot as message

import logging
import os
import re

bot = logging.getLogger("rse.main")
parser_regex = "github"


class Encyclopedia:
    """An encyclopedia is one or more namespaces to store research
       software. By default, we create a structure on the filesystem,
       however an sqlite database (or other) can be used.
    """

    def __init__(self, config_file=None, database=None, generate=False):
        """create a software repository. We take a config file, which should
           sit at the root of the repository, and then parse the subfolders
           accordingly.
        """
        self.config = Config(config_file or RSE_CONFIG_FILE, generate=generate)
        self.config_dir = os.path.dirname(self.config.configfile)
        self.initdb(database)

    def initdb(self, database):
        """setup the rse home (where the config directory is stored) and the
           database specification. If a database string is required (and not
           provided) alert the user and exit on error).

           Arguments:
            - config_dir (str) : the configuration directory (home for rse)
            - database (str) : a string to specify the database setup
        """
        self.database = (
            database
            or RSE_DATABASE
            or self.config.get("DEFAULT", "database")
            or "filesystem"
        )
        database_string = self.config.get("DEFAULT", "databaseconnect")
        bot.info("Database: %s" % self.database)

        # Supported database options
        valid = ("sqlite", "postgresql", "mysql+pymysql", "filesystem")
        if not self.database.startswith(valid):
            bot.warning(
                "%s is not yet a supported type, saving to filesystem." % self.database
            )
            self.database = "filesystem"

        # Create database client with functions for database type
        self.db = init_db(
            self.database,
            config_dir=self.config_dir,
            database_string=database_string,
            config=self.config,
        )

    def exists(self, uid):
        """based on a parser type and unique identifier, determine if software
           exists in the database
        """
        parser = get_parser(uid, config=self.config)
        return self.db.exists(parser.uid)

    def list(self, name=None):
        """A wrapper to the database list_repos function. Optionally take
           a whole parser name (e.g., github) or just a specific uid. No
           parser indicates that we list everything.
        """
        return self.db.list_repos(name)

    def list_criteria(self):
        """Get a listing of criteria from the rse API
        """
        if not hasattr(self, "criteria"):
            self.criteria = get_criteria()
        return self.criteria

    def list_taxonomy(self):
        """Get a listing of a flattened taxonomy from the rse API
        """
        if not hasattr(self, "taxonomy"):
            self.taxonomy = get_taxonomy()
        return self.taxonomy

    def bulk_add(self, filename):
        """Given a filename with a single list of repos, add each
        """
        repos = []
        if os.path.exists(filename):
            for name in read_file(filename):
                uid = name.strip()
                repos += [self.add(uid, quiet=True)] or []
        return repos

    def bulk_update(self, filename):
        """Given a filename with a single list of repos, add each
        """
        repos = []
        if os.path.exists(filename):
            for name in read_file(filename):
                uid = name.strip()
                try:
                    repos += [self.update(uid)]
                except RepoNotFoundError:
                    pass
        return repos

    def add(self, uid, quiet=False):
        """A wrapper to add a repository to the software database.
        """
        if not self.exists(uid):
            repo = self.db.add(uid)
            return repo
        if not quiet:
            bot.error(f"{uid} already exists in the database.")

    def get(self, uid=None):
        """A wrapper to get a repo id from the database. If an id is not provided,
           will return the last updated repo based on timestamp of file or database.
        """
        return self.db.get(uid)

    def get_or_create(self, uid):
        return self.db.get_or_create(uid)

    def clear(self, target=None, noprompt=False):
        """clear takes a target, and that can be a uid, parser, or none
           We ask the user for confirmation.
        """
        # Case 1: no target indicates clearing all
        if not target:
            if noprompt or confirm(
                "This will delete all software in the database, are you sure?"
            ):
                return self.db.clear()

        # Case 2: it's a parser
        elif target in RSE_PARSERS:
            if noprompt or confirm(
                f"This will delete all {target} software in the database, are you sure?"
            ):
                return self.db.delete_parser(target)

        # Case 3, it's a specific software identifier
        elif re.search(parser_regex, target):
            if noprompt or confirm(
                f"This will delete software {target}, are you sure?"
            ):
                return self.db.delete_repo(target)

        else:
            raise RuntimeError(f"Unrecognized {target} to clear")

    def update(self, uid):
        """Update an existing software repository.
        """
        try:
            repo = self.get(uid)
            self.db.update(repo)
            bot.info(f"{repo.uid} has been updated.")
            return repo
        except RepoNotFoundError:
            bot.error(f"{uid} does not exist.")

    def search(self, query):
        """Search across commands and general metadata for a string of interest.
           We use regular expressions (re.search) so they are supported.
           Search is only available for non-filesystem databases.
        """
        results = self.db.search(query)
        if results:
            return results
        bot.info(f"No results matching {query}")

    # Annotation

    def annotate(self, username, atype, unseen_only=True, repo=None, save=False):
        """Annotate the encyclopedia, either for criteria or taxonomy.
           A username is required for the namespace.
 
           Arguments:
            - username (str) : the user's GitHub username
            - atype (str) : the annotation type
            - unseen_only (bool): annotate only items not seen by username
            - repo (str) : annotate a particular software repository
        """
        # git config user.name
        if not username:
            username = get_github_username()

        if atype == "criteria":
            return self.annotate_criteria(username, unseen_only, repo, save)
        elif atype == "taxonomy":
            return self.annotate_taxonomy(username, unseen_only, repo, save)
        bot.error(f"Unknown annotation type, {atype}.")

    def yield_criteria_annotation_repos(self, username, unseen_only=True, repo=None):
        """Given a username, repository, and preference for seen / unseen,
           yield a repository to annotate.
        """
        if repo is None:
            repos = self.list()
        else:
            parser = get_parser(repo, config=self.config)
            repos = [[parser.uid]]
            unseen_only = False

        # yield combinations that don't exist yet, repo first to save changes
        for name in repos:
            repo = self.get(name[0])
            for item in self.list_criteria():
                if unseen_only and not repo.has_criteria_annotation(
                    item["uid"], username
                ):
                    yield repo, item
                elif not unseen_only:
                    yield repo, item

    def yield_taxonomy_annotation_repos(self, username, unseen_only=True, repo=None):
        """Given a username, repository, and preference for seen / unseen,
           yield a repository to annotate.
        """
        if repo is None:
            repos = self.list()
        else:
            parser = get_parser(repo, config=self.config)
            repos = [[parser.uid]]
            unseen_only = False

        # yield combinations that don't exist yet, repo first to save changes
        for name in repos:
            repo = self.get(name[0])
            if unseen_only and not repo.has_taxonomy_annotation(username):
                yield repo
            elif not unseen_only:
                yield repo

    def annotate_criteria(self, username, unseen_only=True, repo=None, save=False):
        """Annotate criteria, meaning we iterate over repos and criteria that 
           match the user request, namely to annotate unseen only, or just
           a particular repository. If the repository is specified, unseen_only
           is assumed False.
        """
        annotations = {}
        last = None
        for repo, criteria in self.yield_criteria_annotation_repos(
            username, unseen_only, repo
        ):

            # Only print repository if not seen yet
            if not last or repo.uid != last.uid:

                # If we have a last repo, we need to save progress
                if last is not None and save is True:
                    last.save_criteria()
                if last is not None:
                    annotations[last.uid] = last.criteria

                message.info(f"\n{repo.url} [{repo.description}]:")
                last = repo

            response = confirm(criteria["name"])
            repo.update_criteria(criteria["uid"], username, response)

        # Save the last repository
        if last is not None and save is True:
            last.save_criteria()
        if last is not None:
            annotations[last.uid] = last.criteria
        return annotations

    def annotate_taxonomy(self, username, unseen_only=True, repo=None, save=False):
        """Annotate taxonomy, meaning we iterate over repos and criteria that 
           match the user request, namely to annotate unseen only, or just
           a particular repository. If the repository is specified, unseen_only
           is assumed False.
        """
        annotations = {}

        # Retrieve the full taxonomy
        items = self.list_taxonomy()
        choices = [str(i) for i, _ in enumerate(items)]
        prefix = "0:%s" % (len(items) - 1)

        for repo in self.yield_taxonomy_annotation_repos(username, unseen_only, repo):

            message.info(f"\n{repo.url} [{repo.description}]:")
            print("How would you categorize this software? [enter one or more numbers]")
            for i, t in enumerate(items):
                example = t.get("example", "")
                name = t.get("name", "")
                if name and example:
                    print(f"[{i}] {name} ({example})")
                elif name:
                    print(f"[{i}] {name}")

            response = choice_prompt(
                "Please enter one or more numbers, separated by spaces",
                choices=choices,
                choice_prefix=prefix,
                multiple=True,
            )

            # Get the unique ids
            uids = [
                items[int(x)]["uid"]
                for x in set(response.split(" "))
                if int(x) < len(items)
            ]
            repo.taxonomy[username] = uids
            repo.save_taxonomy()
            annotations[repo.uid] = repo.taxonomy

        return annotations
