from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from webdriver_manager.chrome import ChromeDriverManager


import threading
import sys
import tty
import termios
import signal
import os
import time
import pathlib
import subprocess
from getpass import getpass

import argparse


class DownloaderDaemon:
    def __init__(
            self,
            ident: str,
            pin: str,
            project: str,
            password: str,
            login_url: str,
            download_button_id: str,
            xfreerdp_command: str,
            xfreerdp_args: str,
            download_dir: str,
            launcher_rename: str,
            # driver_path: str,
            headless: bool,
            timeout: int,
    ):

        self.ident = ident
        self.pin = pin
        self.project = project
        self.password = password
        self.login_url = login_url
        self.download_button_id = download_button_id
        self.xfreerdp_command = xfreerdp_command
        self.xfreerdp_args = xfreerdp_args
        self.download_dir = os.path.expanduser(download_dir)
        self.launcher_rename = launcher_rename
        self.timeout = timeout
        
        self.bash_command = " ".join([self.xfreerdp_command,
                                      self.download_dir + self.launcher_rename,
                                      "/u:" + self.ident + self.project +
                                      "@dstfse.local",
                                      "/p:" + self.password,
                                      self.xfreerdp_args])

        options = Options()
        if headless:
            options.add_argument('--headless=new')  # Use new headless mode

        prefs = {
            "download.default_directory": str(self.download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)


    # Login
    def login(self) -> None:
        print("Login to remote.dst")
        self.driver.get(self.login_url)

        ident_field = self.driver.find_element(By.NAME, "username")
        ident_field.send_keys(self.ident, Keys.TAB, self.pin,
                              Keys.TAB, Keys.ENTER)

        sms_code = input("SMS code: ")

        sms_field = self.driver.find_element(By.NAME, "_F5_challenge")
        sms_field.send_keys(sms_code, Keys.ENTER)

    # Download
    def download(self) -> None:
        print("Started download rdp-file...")
        download_button = self.driver.find_element(
            By.ID, self.download_button_id
        )
        download_button.click()

        time.sleep(2)

        dir_path = pathlib.Path(self.download_dir)
        files = [f for f in dir_path.glob("*") if f.is_file()]

        if not files:
            print(
                f"⚠ No files found in: {dir_path}, download probably failed."
            )
            return

        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        new_name = self.launcher_rename
        target_path = dir_path / new_name

        if target_path.exists():
            target_path.unlink()

        latest_file.rename(target_path)
        print(f"✅ Downloaded and renamed {latest_file.name} → {new_name}")

    def run_xfreerdp(self) -> None:

        print("🚀 Starting xfreerdp...")

        os.system(self.bash_command)
        # subprocess.Popen(command, shell=True)
        print("xfreerdp process terminated.")

    def print_xfreerdp_bash_command(self) -> None:

        print(self.bash_command)

    def automatic(self) -> None:
        try:
            self.download()
            time.sleep(self.timeout)
            self.run_xfreerdp()

        except Exception:
            print("⚠ First entering attempt failed, "
                  "will try to login from scratch.")
            try:
                self.login()
                time.sleep(self.timeout)
                self.download()
                time.sleep(self.timeout)
                self.run_xfreerdp()

            except Exception:
                print("⚠ Second entering attempt failed, "
                      "try to do each step manually or restart.")

    def close(self):
        self.driver.quit()


def show_menu():
    print("\nAvailable commands:")
    print("  [l] login to remote.dst.dk")
    print("  [d] download")
    print("  [x] run xfreedrp command")
    print("  [p] print xfreedrp command")
    print("  [a] automatic")
    print("  [q] quit")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Automatized login to DST."
    )

    # Required positional args
    parser.add_argument("ident",
                        help="DST ident (four letters)")
    parser.add_argument("pin",
                        help="DST PIN code (four numbers)")
    parser.add_argument("project",
                        help="DST project name (six numbers)")

    # Optional password (prompted if not given)
    parser.add_argument("--password",
                        help="DST password (prompted if omitted)")

    # Optional keyword args
    parser.add_argument("--login-url",
                        default="https://remote.dst.dk/",
                        help="Login URL")
    parser.add_argument("--download-button-id",
                        default="/Common/dst-RDP_FSE_Windows",
                        help="Identifier for the download button")
    parser.add_argument("--xfreerdp-command",
                        default="xfreerdp",
                        help="xfreerdp command")
    parser.add_argument("--xfreerdp-args",
                        default="/size:1800x1050",
                        help="Arguments for xfreerdp basides file, username, and password. E.g., /size:, /scale:...")
    parser.add_argument("--download-dir",
                        default="~/tmp/",
                        help="Download directory")
    parser.add_argument("--launcher-rename",
                        default="dst-launcher.rdp",
                        help="Launcher rename target")
    parser.add_argument("--raw-init",
                        dest="raw_init",
                        action="store_true",
                        help="Start session without automatic login attempt")
    parser.set_defaults(raw_init=False)
    parser.add_argument("--visual",
                        dest="headless",
                        action="store_false",
                        help="Show the browser")
    parser.set_defaults(headless=True)
    parser.add_argument("--timeout",
                        type=int,
                        default=1,
                        help="Timeout in seconds")

    return parser.parse_args()


def main():

    args = parse_args()

    if not args.password:
        args.password = getpass("Enter DST password: ")

    argdict = vars(args).copy()
    argdict.pop("raw_init", None)

    d = DownloaderDaemon(**argdict)

    if not args.raw_init:

        print("Attempting automatic entering")
        d.login()
        time.sleep(d.timeout)
        d.download()
        time.sleep(d.timeout)
        d.run_xfreerdp()

    while True:
        show_menu()
        choice = input("Select option: ").strip().lower()

        if choice in ("l", "login"):
            d.login()
        elif choice in ("d", "download"):
            d.download()
        elif choice in ("q", "quit", "exit"):
            d.close()
            return
        elif choice in ("x", "xfreerdp"):
            d.run_xfreerdp()
        elif choice in ("p", "print"):
            d.print_xfreerdp_bash_command()
        elif choice in ("a", "automatic"):
            d.automatic()
        else:
            print("❓ Unknown option:", choice)


if __name__ == "__main__":
    main()
