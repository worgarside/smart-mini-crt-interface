"""Class for the creation, caching, and management of artwork images."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from re import compile as compile_regex

from PIL.Image import Image, Resampling
from PIL.Image import open as open_image
from requests import get
from wg_utilities.loggers import get_streaming_logger

LOGGER = get_streaming_logger(__name__)


class ArtworkImage:
    """Class for the creation, caching, and management of artwork images."""

    ARTWORK_DIR = Path.home() / "crt_artwork"
    ALPHANUM_PATTERN = compile_regex(r"[\W_]+")

    def __init__(self, album: str, artist: str, url: str) -> None:
        self.ARTWORK_DIR.mkdir(exist_ok=True)

        self.album = album
        self.artist = artist or "unknown"
        self.url = url

    def download(self) -> None:
        """Download the image from the URL to store it locally for future use."""
        self.ARTWORK_DIR.joinpath(self.artist_directory).mkdir(
            exist_ok=True,
            parents=True,
        )

        if Path(self.url).is_file():
            LOGGER.debug("Opening local image: %s", self.url)
            with Path(self.url).open("rb") as fin:
                artwork_bytes = fin.read()
        else:
            LOGGER.debug("Downloading artwork from remote URL: %s", self.url)
            artwork_bytes = get(self.url, timeout=30).content

        with self.file_path.open("wb") as fout:
            fout.write(artwork_bytes)

        LOGGER.info("New image saved at %s", self.file_path)

    def get_image(self, size: int | None = None) -> Image:
        """Returns the image as a PIL Image object, with optional resizing.

        Args:
            size (int): integer value to use as height and width of artwork, in pixels

        Returns:
            Image: PIL Image object of artwork
        """
        LOGGER.debug("Getting image with size %i", size)

        if not self.file_path.exists():
            self.download()

        with self.file_path.open("rb") as fin:
            tk_img = open_image(BytesIO(fin.read()))

        if size is not None:
            tk_img = tk_img.resize((size, size), Resampling.LANCZOS)

        return tk_img

    @property
    def artist_directory(self) -> str:
        """Format the artist name for use as directory name.

        Returns:
            str: the artist name, with all non-alphanumeric characters removed
        """
        return ArtworkImage.ALPHANUM_PATTERN.sub("", self.artist).lower()

    @property
    def filename(self) -> str:
        """Format the album name for use as the file name.

        Returns:
            str: the filename of the artwork image
        """
        return ArtworkImage.ALPHANUM_PATTERN.sub("", self.album).lower() + ".png"

    @property
    def file_path(self) -> Path:
        """Returns the fully-qualified path to the artwork image.

        Returns:
            str: artwork image path
        """
        return self.ARTWORK_DIR / self.artist_directory / self.filename

    def __str__(self) -> str:
        """Return the string representation of the object."""
        return self.__repr__()

    def __repr__(self) -> str:
        """Return the string representation of the object."""
        return f"ArtworkImage({self.artist}, {self.album}, {self.url})"
