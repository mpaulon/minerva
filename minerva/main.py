import argparse
import tomllib
import io
import logging
import shutil
from pathlib import Path

import jinja2
from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin

logger = logging.getLogger("minerva")


class Minerva:

    _output_folder: Path
    _jinja_environment: jinja2.Environment

    _md = MarkdownIt("commonmark", {"breaks": True, "html": True}).use(
        front_matter_plugin
    )

    def __init__(self, config: dict, folder: Path):
        self._folder = folder
        self._load_config(config)

    def _load_config(self, config: dict):
        logger.info("Loading minerva config")
        self._config = config["settings"]

    def _ignore_folder(self, folder: Path):
        with open(folder / ".gitignore", "w") as _gitignore:
            _gitignore.write("*")

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
        self._ignore_folder(self._output_folder)
        (self._output_folder / "posts").mkdir(exist_ok=True)
        shutil.copytree(
            self._folder / "themes" / self._config["theme"] / "assets",
            self._output_folder / "assets",
        )

    def _build_index(self, posts: dict):
        logger.info("Building blog index page")
        template = self._jinja_environment.get_template("index.html.j2")
        with open(self._output_folder / "index.html", "w") as index:
            index.write(
                template.render(
                    metadata=self._config["metadata"][self._config["language"]],
                    posts=posts
                )
            )

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
        with open(self._output_folder / "posts" / f"{filename}.html", "w") as out:
            out.write(
                template.render(
                    content=self._md.render(content_str),
                    post_metadata=metadata,
                    metadata=self._config["metadata"][self._config["language"]],
                )
            )
        return metadata

    def _build_posts(self) -> dict:
        logger.info("Building blog articles")
        template = self._jinja_environment.get_template("post.html.j2")
        posts = {}
        for post_md_file in (self._folder / "posts").iterdir():
            if post_md_file.is_dir():
                continue
            with open(post_md_file, "r") as post_md:
                posts[post_md_file.stem] = self._build_post(
                    post_md_file.stem, post_md, template
                )
        self._build_posts_data()
        return posts

    def _build_posts_data(self):
        logger.info("Building posts data/assets")
        post_data_folder = self._folder / "posts" / "data"
        if post_data_folder.exists():
            shutil.copytree(
                post_data_folder, self._output_folder / "posts" / "data"
            )
            return
        logger.warning("No posts data/assets folder found")

    def _build_pagefind(self):
        return

    def build(self, clean: bool = False):
        logger.info("Building blog")
        self._create_output(clean)
        self._create_jinja_loader()
        posts = self._build_posts()
        self._build_index(posts)
        if self._config.get("pagefind", False):
            self._build_pagefind()


def run():
    parser = argparse.ArgumentParser(prog="minerva", description="simple blog engine")
    parser.add_argument("--folder", "-f", type=Path, help="blog folder")
    parser.add_argument("--config", "-c", type=Path, help="config file path")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="enable debug logging"
    )

    subparser = parser.add_subparsers(dest="action", required=True)
    build_parser = subparser.add_parser("build")
    build_parser.add_argument(
        "--clean", action="store_true", help="cleanup build directory before building"
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

    with open(config_path, "rb") as config_file:
        config = tomllib.load(config_file)

    if args.action == "build":
        Minerva(config, folder_path).build(clean=args.clean)


if __name__ == "__main__":
    run()
