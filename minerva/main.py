import argparse
import tomllib
import io
import logging
from pathlib import Path
import shutil
import subprocess
import tarfile

import jinja2
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_figure import figure_plugin
import requests

from . import constants

logger = logging.getLogger("minerva")


def ignore_folder(folder: Path):
    with open(folder / ".gitignore", "w") as _gitignore:
        _gitignore.write("*")


class Minerva:

    _output_folder: Path
    _jinja_environment: jinja2.Environment

    _md = (
        MarkdownIt("commonmark", {"breaks": True, "html": True})
        .use(front_matter_plugin)
        .use(figure_plugin)
        .use(footnote_plugin)
    )

    def __init__(self, config: dict, folder: Path):
        self._folder = folder
        self._load_config(config)

    @property
    def output_folder(self):
        return self._output_folder

    def _load_config(self, config: dict):
        logger.info("Loading minerva config")
        self._config = config["settings"]

    def _render(self, template: jinja2.Template, output: Path, **variables):
        with open(output, "w", encoding="utf-8") as _out:
            _out.write(
                template.render(
                    metadata=self._config["metadata"][self._config["language"]],
                    settings=self._config,
                    **variables,
                )
            )

    def _create_jinja_loader(self):
        self._jinja_environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                self._folder / "themes" / self._config["theme"] / "templates"
            ),
            autoescape=jinja2.select_autoescape(),
        )

    def _create_output(self, clean: bool = False):
        self._output_folder = self._folder / "build"
        if clean:
            logger.info("Cleaning existing output folder at %s", self._output_folder)
            shutil.rmtree(self._output_folder, ignore_errors=True)
        logger.info("Creating output folder at %s", self._output_folder)
        self._output_folder.mkdir(exist_ok=True)
        ignore_folder(self._output_folder)
        (self._output_folder / "posts").mkdir(exist_ok=True)
        shutil.copytree(
            self._folder / "themes" / self._config["theme"] / "assets",
            self._output_folder / "assets",
            dirs_exist_ok=True,
        )

    def _build_index(self, posts: dict):
        logger.info("Building blog index page")
        template = self._jinja_environment.get_template("index.html.j2")
        self._render(template, self._output_folder / "index.html", posts=posts)

    def _parse_meta(self, content: str):
        metadata = {}
        for line in content.split("\n"):
            meta_key, meta_value = line.split(":", 1)
            metadata[meta_key.strip()] = meta_value.strip()
        return metadata

    def _build_post(
        self, filename: str, content: io.TextIOWrapper, template: jinja2.Template
    ):
        content_str = content.read()
        tokens = self._md.parse(content_str)
        if tokens[0].type == "front_matter":
            metadata = self._parse_meta(tokens[0].content)
        else:
            raise RuntimeError(f"Missing metadata for post {filename}")
        self._render(
            template,
            self._output_folder / "posts" / f"{filename}.html",
            content=self._md.render(content_str),
            post_metadata=metadata,
        )
        return metadata

    def _build_posts(self) -> dict:
        logger.info("Building blog articles")
        template = self._jinja_environment.get_template("post.html.j2")
        posts = {}
        for post_md_file in (self._folder / "posts").iterdir():
            if post_md_file.is_dir():
                continue
            logger.info("Building %s", post_md_file)
            with open(post_md_file, "r") as post_md:
                posts[post_md_file.stem] = self._build_post(
                    post_md_file.stem, post_md, template
                )
        self._build_posts_data()
        return posts

    def _build_posts_data(self):
        logger.info("Building posts/data/assets")
        post_data_folder = self._folder / "posts" / "data"
        if post_data_folder.exists():
            shutil.copytree(
                post_data_folder,
                self._output_folder / "posts" / "data",
                dirs_exist_ok=True,
            )
            return
        logger.warning("No posts/data/assets folder found")

    def _build_pagefind(self):
        logger.info("Building search page")
        template = self._jinja_environment.get_template("search.html.j2")
        self._render(template, self._output_folder / "search.html")

    def _build_posts_list(self, posts: dict):
        logger.info("Building posts list")
        template = self._jinja_environment.get_template("list.html.j2")
        self._render(template, self._output_folder / "list.html", posts=posts)

    def _build_404(self):
        logger.info("Building 404 page")
        template = self._jinja_environment.get_template("404.html.j2")
        self._render(template, self._output_folder / "404.html")

    def build(self, clean: bool = False):
        logger.info("Building blog")
        self._create_output(clean)
        self._create_jinja_loader()
        posts = self._build_posts()
        self._build_index(posts)
        self._build_posts_list(posts)
        if self._config.get("pagefind", False):
            self._build_pagefind()
        self._build_404()


def download_pagefind(tools_path: Path, force: bool = False):
    tools_path.mkdir(parents=True, exist_ok=True)
    ignore_folder(tools_path)
    pagefind_archive_path = tools_path / "pagefind.tar.gz"

    if not force and (tools_path / constants.PAGEFIND_BINARY).exists():
        logger.info("Pagefind binary found")
        return

    logger.info("Pagefind binary not found")
    logger.info("Downloading pagefind from %s", constants.PAGEFIND_URL)
    with requests.get(constants.PAGEFIND_URL, stream=True) as r:
        with open(pagefind_archive_path, "wb") as f:
            shutil.copyfileobj(r.raw, f)

    logger.info("Extracting pagefind from %s", pagefind_archive_path)

    tar = tarfile.open(pagefind_archive_path, "r:gz")
    tar.extractall(pagefind_archive_path.parent)
    tar.close()

    logger.info("Removing pagefind archive")

    pagefind_archive_path.unlink()


def run():
    parser = argparse.ArgumentParser(prog="minerva", description="simple blog engine")
    parser.add_argument("--folder", "-f", type=Path, help="blog folder")
    parser.add_argument("--config", "-c", type=Path, help="config file path")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="enable debug logging"
    )

    subparsers = parser.add_subparsers(dest="action", required=True)
    pagefind_parser = subparsers.add_parser("pagefind")
    pagefind_parser.add_argument(
        "--build",
        action="store_true",
        help="re-build site before indexing with pagefind",
    )
    pagefind_parser.add_argument(
        "--version", action="store_true", help="display pagefind version"
    )
    pagefind_parser.add_argument(
        "--update", action="store_true", help="force download pagefind version"
    )

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--serve-port", type=int, default=8000, required=False)

    # global arguments
    for subparser in [pagefind_parser, build_parser]:

        subparser.add_argument(
            "--clean",
            action="store_true",
            help="cleanup build directory before building",
        )
        subparser.add_argument(
            "--serve",
            action="store_true",
            help="serve the static site on localhost with the specified port",
        )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    stderr_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] - %(name)s - %(message)s"
    )
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(stderr_formatter)
    logger.addHandler(stderr_handler)

    folder_path: Path = args.folder or Path(".")
    config_path: Path = args.config or folder_path / "settings.toml"
    tools_path: Path = folder_path / "tools"

    with open(config_path, "rb") as config_file:
        config = tomllib.load(config_file)

    builder = Minerva(config, folder_path)

    if args.action == "pagefind":
        download_pagefind(tools_path, force=args.update)

        if args.build:
            builder.build(clean=args.clean)

        pagefind_command = [
            (tools_path / constants.PAGEFIND_BINARY).as_posix(),
            "--site",
            (folder_path / "build").as_posix(),
        ]
        if args.version:
            pagefind_command.append("--version")
        if args.serve:
            pagefind_command.append("--serve")

        subprocess.run(pagefind_command)

    elif args.action == "build":
        builder.build(clean=args.clean)

        if args.serve:
            import http.server
            import socketserver

            MinervaRequestHandler = http.server.SimpleHTTPRequestHandler
            MinervaRequestHandler.extensions_map[".html"] = "text/html;charset=UTF-8"
            with socketserver.TCPServer(
                ("", args.serve_port),
                lambda request, client_address, server: MinervaRequestHandler(
                    request, client_address, server, directory=builder.output_folder
                ),
            ) as httpd:
                httpd.allow_reuse_address = True
                logger.info("Serving on port %s", args.serve_port)
                httpd.serve_forever()


if __name__ == "__main__":
    run()
