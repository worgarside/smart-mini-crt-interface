"""Class for the creation, caching, and management of artwork images"""
from __future__ import annotations

from io import BytesIO
from os import mkdir
from os.path import exists, isdir, join
from pathlib import Path
from re import compile as compile_regex

from PIL.Image import ANTIALIAS, Image
from PIL.Image import open as open_image
from requests import get


class ArtworkImage:
    """Class for the creation, caching, and management of artwork images"""

    ARTWORK_DIR = Path.home() / "crt_artwork"
    ALPHANUM_PATTERN = compile_regex(r"[\W_]+")

    def __init__(self, album: str, artist: str, url: str) -> None:
        if not isdir(self.ARTWORK_DIR):
            mkdir(self.ARTWORK_DIR)

        self.album = album
        self.artist = artist or "unknown"
        self.url = url

    def download(self) -> None:
        """Download the image from the URL to store it locally for future use"""

        if not isdir(self.ARTWORK_DIR / self.artist_directory):
            mkdir(self.ARTWORK_DIR / self.artist_directory)

        artwork_bytes = get(self.url).content

        with open(self.file_path, "wb") as fout:
            fout.write(artwork_bytes)

    def get_image(self, size: int | None = None) -> Image:
        """Returns the image as a PIL Image object, with optional resizing

        Args:
            size (int): integer value to use as height and width of artwork, in pixels

        Returns:
            Image: PIL Image object of artwork
        """

        if not exists(self.file_path):
            self.download()

        with open(self.file_path, "rb") as fin:
            tk_img = open_image(BytesIO(fin.read()))

        if size is not None:
            tk_img = tk_img.resize((size, size), ANTIALIAS)

        return tk_img

    @property
    def artist_directory(self) -> str:
        """Strips all non-alphanumeric characters from the artist name for use as the
        directory name

        Returns:
            str: the artist name, with all non-alphanumeric characters removed
        """
        return ArtworkImage.ALPHANUM_PATTERN.sub("", self.artist).lower()

    @property
    def filename(self) -> str:
        """Strip all non-alphanumeric characters from the album name for use as the
        file name

        Returns:
            str: the filename of the artwork image
        """
        return ArtworkImage.ALPHANUM_PATTERN.sub("", self.album).lower() + ".png"

    @property
    def file_path(self) -> str:
        """
        Returns:
            str: fully-qualified path to the artwork image
        """
        return join(self.ARTWORK_DIR, self.artist_directory, self.filename)
