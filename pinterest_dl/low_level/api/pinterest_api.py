import re
from typing import List, Optional, Tuple

import requests

from pinterest_dl.data_model.cookie import PinterestCookieJar
from pinterest_dl.exceptions import (
    InvalidBoardUrlError,
    InvalidPinterestUrlError,
    InvalidSearchUrlError,
    InvalidProfileUrlError,
)
from pinterest_dl.low_level.api.endpoints import Endpoint
from pinterest_dl.low_level.api.pinterest_response import PinResponse
from pinterest_dl.low_level.http.request_builder import RequestBuilder


class PinterestAPI:
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36"
    )

    def __init__(
        self,
        url: str,
        cookies: Optional[PinterestCookieJar] = None,
        timeout: float = 5,
    ) -> None:
        """Pinterest API client.

        Args:
            url (str): Pinterest URL. (e.g. "https://www.pinterest.com/pin/123456789/")
            cookies (Optional[PinterestCookieJar], optional): Pinterest cookies. Defaults to None.
            timeout (float, optional): Request timeout in seconds. Defaults to 5.
        """
        self.url = url
        self.timeout = timeout

        # Parse pin ID
        try:
            self.pin_id = self._parse_pin_id(self.url)
        except InvalidPinterestUrlError:
            self.pin_id = None
            try:
                self.query = self._parse_search_query(self.url)
            except InvalidSearchUrlError:
                pass

        # Parse board URL
        try:
            self.username, self.boardname = self._parse_board_url(self.url)
        except InvalidBoardUrlError:
            self.username = None
            self.boardname = None

        # Parse profile URL (if not a board)
        if not self.boardname:
            try:
                self.profile_username = self._parse_profile_url(self.url)
            except InvalidProfileUrlError:
                self.profile_username = None
        else:
            self.profile_username = None

        self.endpoint = Endpoint()
        self.cookies = cookies if cookies else self._get_default_cookies(self.endpoint._BASE)

        # Initialize session
        self._session = requests.Session()
        self._session.cookies.update(self.cookies)  # Update session cookies
        self._session.headers.update({"User-Agent": self.USER_AGENT})
        self._session.headers.update(
            {"x-pinterest-pws-handler": "www/pin/[id].js"}
        )  # required since 2025-03-07. See https://github.com/sean1832/pinterest-dl/issues/30
        self.is_pin = bool(self.pin_id)
        self.is_profile = bool(self.profile_username)

    def get_related_images(self, num: int, bookmark: List[str]) -> PinResponse:
        if not self.pin_id:
            raise ValueError("Invalid Pinterest URL")
        if num < 1:
            raise ValueError("Number of images must be greater than 0")
        if num > 50:
            raise ValueError("Number of images must not exceed 50 per request")

        endpoint = self.endpoint.GET_RELATED_MODULES
        source_url = f"/pin/{self.pin_id}/"
        options = {
            "pin_id": f"{self.pin_id}",
            "context_pin_ids": [],
            "page_size": num,
            "bookmarks": bookmark,
            "search_query": "",
            "source": "deep_linking",
            "top_level_source": "deep_linking",
            "top_level_source_depth": 1,
            "is_pdp": False,
        }
        try:
            request_url = RequestBuilder.build_get(endpoint, options, source_url)
            response_raw = self._session.get(request_url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise requests.RequestException(f"Failed to request related images: {e}")

        try:
            response_raw_json = response_raw.json()
        except requests.exceptions.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to decode JSON response: {e}. Response: {response_raw.text}"
            )

        return PinResponse(request_url, response_raw_json)

    def get_main_image(self) -> PinResponse:
        if not self.pin_id:
            raise ValueError("Invalid Pinterest URL")
        endpoint = self.endpoint.GET_MAIN_IMAGE

        source_url = f"/pin/{self.pin_id}/"
        options = {
            "url": "/v3/users/me/recent/engaged/pin/stories/",
            "data": {
                "fields": "pin.description,pin.id,pin.images[236x]",
                "pin_preview_count": 1,
            },
        }

        try:
            request_url = RequestBuilder.build_get(endpoint, options, source_url)
            response_raw = self._session.get(request_url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise requests.RequestException(f"Failed to request main image: {e}")

        return PinResponse(request_url, response_raw.json())

    def get_board(self) -> PinResponse:
        if not self.username or not self.boardname:
            username, boardname = self._parse_board_url(self.url)
        else:
            username, boardname = self.username, self.boardname

        endpoint = self.endpoint.GET_BOARD_RESOURCE

        source_url = f"/{username}/{boardname}/"
        options = {
            "username": username,
            "slug": boardname,
            "field_set_key": "detailed",
        }

        try:
            request_url = RequestBuilder.build_get(endpoint, options, source_url)
            response_raw = self._session.get(request_url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise requests.RequestException(f"Failed to request board: {e}")

        return PinResponse(request_url, response_raw.json())

    def get_board_feed(self, board_id: str, num: int, bookmark: List[str]) -> PinResponse:
        self._validate_num(num)

        board_url = f"/{self.username}/{self.boardname}/"

        endpoint = self.endpoint.GET_BOARD_FEED_RESOURCE
        source_url = board_url
        options = {
            "board_id": board_id,
            "board_url": board_url,
            "page_size": num,
            "bookmarks": bookmark,
            "currentFilter": -1,
            "field_set_key": "react_grid_pin",  # "react_grid_pin" | "grid_item" | "board_pin"
            "filter_section_pins": True,  # flag to tell the server to filter section pins
            "sort": "default",  # "default" | "newest" | "oldest" | "popular"
            "layout": "default",  # "default" | "custom"
            "redux_normalize_feed": True,  # flag to tell the server to return the data in a format that is easy to use in the frontend
        }

        try:
            request_url = RequestBuilder.build_get(endpoint, options, source_url)
            response_raw = self._session.get(request_url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise requests.RequestException(f"Failed to request board feed: {e}")

        return PinResponse(request_url, response_raw.json())

    def get_search(self, num: int, bookmark: List[str]) -> PinResponse:
        if not self.query:
            raise ValueError("Invalid Pinterest search URL")
        self._validate_num(num)

        source_url = f"/search/pins/?q={self.query}rs=typed"

        endpoint = self.endpoint.GET_SEARCH_RESOURCE
        options = {
            "appliedProductFilters": "---",
            "auto_correction_disabled": False,
            "bookmarks": bookmark,
            "page_size": num,
            "query": self.query,
            "redux_normalize_feed": True,
            "rs": "typed",  # is user typed or not
            "scope": "pins",
            "source_url": source_url,
        }

        try:
            request_url = RequestBuilder.build_get(endpoint, options, source_url)
            response_raw = self._session.get(request_url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise requests.RequestException(f"Failed to request search: {e}")
        try:
            json_response = response_raw.json()
        except requests.exceptions.JSONDecodeError as e:
            print(response_raw.text)
            raise requests.JSONDecodeError(f"Failed to decode JSON response: {e}")
        return PinResponse(request_url, json_response)

    def get_user_pins(self, username: str, num: int, bookmark: List[str]) -> PinResponse:
        """Get pins created by a user.

        Args:
            username (str): Pinterest username.
            num (int): Maximum number of pins to retrieve.
            bookmark (List[str]): Pagination bookmarks.

        Returns:
            PinResponse: Response containing user's pins.
        """
        self._validate_num(num)

        source_url = f"/{username}/_created/"

        endpoint = self.endpoint.GET_USER_ACTIVITY_PINS_RESOURCE
        options = {
            "username": username,
            "page_size": num,
            "bookmarks": bookmark,
            "field_set_key": "grid_item",
            "include_archived": True,
        }

        try:
            request_url = RequestBuilder.build_get(endpoint, options, source_url)
            response_raw = self._session.get(request_url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise requests.RequestException(f"Failed to request user pins: {e}")

        try:
            json_response = response_raw.json()
        except requests.exceptions.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to decode JSON response: {e}. Response: {response_raw.text}"
            )

        return PinResponse(request_url, json_response)

    def _validate_num(self, num: int) -> None:
        if num < 1:
            raise ValueError("Number of images must be greater than 0")
        if num > 50:
            raise ValueError("Number of images must not exceed 50 per request")

    @staticmethod
    def _get_default_cookies(url: str) -> dict:
        try:
            response = requests.get(url)
            return response.cookies.get_dict()
        except requests.exceptions.RequestException as e:
            raise requests.RequestException(f"Failed to get default cookies: {e}")

    @staticmethod
    def _parse_pin_id(url: str) -> str:
        result = re.search(r"pin/(\d+)/", url)
        if not result:
            raise InvalidPinterestUrlError(f"Invalid Pinterest URL: {url}")
        return result.group(1)

    @staticmethod
    def _parse_search_query(url: str) -> str:
        # /search/pins/?q={query}%26rs=typed
        result = re.search(r"/search/pins/\?q=([A-Za-z0-9%]+)&rs=typed", url)
        if not result:
            raise InvalidSearchUrlError(f"Invalid Pinterest search URL: {url}")
        query = result.group(1)
        return RequestBuilder.url_decode(query)

    @staticmethod
    def _parse_board_url(url: str) -> Tuple[str, str]:
        """Parse Pinterest board URL to username and boardname.

        Args:
            url (str): Pinterest board URL. (e.g. "https://www.pinterest.com/username/boardname/")

        Returns:
            result (str, str): (username, boardname)
        """
        result = re.search(
            r"https://(?:[a-z0-9-]+\.)?pinterest\.com/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)/?$", url
        )
        if not result:
            raise InvalidBoardUrlError(f"Invalid Pinterest board URL: {url}")
        return result.group(1), result.group(2)

    @staticmethod
    def _parse_profile_url(url: str) -> str:
        """Parse Pinterest profile URL to username.

        Args:
            url (str): Pinterest profile URL. (e.g. "https://www.pinterest.com/username/")

        Returns:
            result (str): username
        """
        result = re.search(
            r"https://(?:[a-z0-9-]+\.)?pinterest\.com/([A-Za-z0-9_-]+)/?$", url
        )
        if not result:
            raise InvalidProfileUrlError(f"Invalid Pinterest profile URL: {url}")
        return result.group(1)
