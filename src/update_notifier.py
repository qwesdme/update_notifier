import datetime
import os
from importlib.metadata import Distribution
from pathlib import Path

from artifacts_keyring import ArtifactsKeyringBackend
from azure.devops.connection import Connection
from azure.devops.released.feed import Feed, FeedClient, Package, MinimalPackageVersion
from colorama import init, Fore, Style
from keyring.credentials import SimpleCredential
from msrest.authentication import BasicAuthentication
from packaging import version


class UpdateNotifier:
    DEBUG = False

    def __init__(
            self,
            organization,
            project,
            feed_name,
            package_name,
            username
    ):
        self.organization: str = organization
        self.project: str = project
        self.feed_name: str = feed_name
        self.package_name: str = package_name
        self.username: str = username

        self._last_checked_file_path = Path.home() / f".{package_name}" / "update" / "last_checked.txt"

        self._feed_client: FeedClient | None = None
        init()

    def _get_pat(self) -> str:
        akb = ArtifactsKeyringBackend()
        url = f"https://pkgs.dev.azure.com/{self.organization}/{self.project}/_packaging/{self.feed_name}/pypi/simple/"
        cred: SimpleCredential | None = akb.get_credential(url, self.username)
        if cred is not None:
            return cred.password
        raise Exception("Error getting credential")

    def _get_feed_client(self) -> FeedClient:
        if self._feed_client is None:
            credentials: BasicAuthentication = BasicAuthentication("", self._get_pat())
            connection: Connection = Connection(
                base_url=f"https://dev.azure.com/{self.organization}",
                creds=credentials
            )
            self._feed_client = connection.clients.get_feed_client()
        return self._feed_client

    def _get_feed_id(self) -> str:
        feeds: list[Feed] = self._get_feed_client().get_feeds(project=self.project)

        for feed in feeds:
            if feed.name == self.feed_name:
                return feed.id

        raise Exception(f"Error getting feed id for feed name '{self.feed_name}'")

    def _get_package_info(self) -> Package:
        packages: list[Package] = self._get_feed_client().get_packages(
            project=self.project,
            feed_id=self._get_feed_id(),
            package_name_query=self.package_name
        )

        for package in packages:
            if package.name == self.package_name:
                return package

        raise Exception(f"Error getting package info for package name '{self.package_name}'")

    def _get_latest_version(self) -> str | None:
        package = self._get_package_info()
        versions: list[MinimalPackageVersion] = package.versions

        for v in versions:
            if v.is_latest:
                return v.version

        return None

    def _get_current_version(self) -> str | None:
        try:
            distribution: Distribution = Distribution.from_name(self.package_name)
            return distribution.version

        except Exception as e:
            print(
                f"{Fore.RED}{Style.BRIGHT}Unable to get the current installed version of {self.package_name}"
                f"The package might have not been installed in a different way{Fore.RESET}"
            )
            if self.DEBUG:
                print(f"{Fore.RED}{e}{Fore.RESET}")
            return None

    def _should_check(self):
        try:
            with open(self._last_checked_file_path, "r") as file:
                content = file.read().strip()
                try:
                    file_date = datetime.datetime.strptime(content, "%Y-%m-%d").date()
                    current_date = datetime.date.today()
                    return (current_date - file_date).days > 1
                except ValueError as ve:
                    if self.DEBUG:
                        print(f"{Fore.RED}{ve}{Fore.RESET}")
                    return True
        except FileNotFoundError as fe:
            if self.DEBUG:
                print(f"{Fore.RED}{fe}{Fore.RESET}")
            return True

    def _update_last_checked(self):
        try:
            os.makedirs(self._last_checked_file_path.parent, exist_ok=True)
            with open(self._last_checked_file_path, "w") as file:
                file.write(datetime.date.today().strftime("%Y-%m-%d"))
        except IOError as e:
            print(f"{Fore.RED}{Style.BRIGHT}Update Notifier Error: Unable to save last checked date{Fore.RESET}")
            if self.DEBUG:
                print(f"{Fore.RED}{e}{Fore.RESET}")

    def check_for_update(self):
        if self._should_check():
            try:
                latest_version = self._get_latest_version()
                current_version = self._get_current_version()

                if None not in [current_version, latest_version]:
                    if version.parse(current_version) >= version.parse(latest_version):
                        print(
                            f"{Fore.GREEN}{Style.BRIGHT}{self.package_name} is up-to-date"
                            f" (version {current_version}){Fore.RESET}"
                        )
                    else:
                        print(
                            f"{Fore.YELLOW}{Style.BRIGHT}Please run the following command to update {self.package_name}"
                            f" to the latest version ({current_version} -> {latest_version}):{Fore.RESET}\n"
                        )
                        print(f"pip install {self.package_name}=={latest_version}\n")
                    self._update_last_checked()

            except Exception as e:
                print(f"{Fore.RED}{Style.BRIGHT}Error checking for update for {self.package_name}{Fore.RESET}")
                if self.DEBUG:
                    print(f"{Fore.RED}{Style.BRIGHT}{e}{Fore.RESET}")
