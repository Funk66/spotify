import webbrowser
from base64 import b64encode
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from json import dumps, loads
from logging import getLogger
from threading import Thread
from time import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, overload
from urllib.parse import quote, urlencode

from certifi import where
from urllib3 import PoolManager
from urllib3.response import HTTPResponse

from .config import Config

if TYPE_CHECKING:
    from socketserver import BaseServer


class SpotifyError(Exception):
    pass


@dataclass(frozen=True)
class SpotifyTrack:
    artist: str
    title: str
    album: str
    uri: str


class Client:
    accounts_url = "https://accounts.spotify.com"
    api_url = "https://api.spotify.com/v1"
    redirect_uri = "http://localhost:8888"

    def __init__(self):
        if not (Config.client and Config.secret):
            raise Exception("Missing Spotify client credentials")
        self.client = PoolManager(ca_certs=where())

    def response(
        self, response: HTTPResponse, success_code: int = 200
    ) -> Dict[str, Any]:
        if response.status != success_code:
            raise SpotifyError(
                f"Failed with code {response.status}: "
                f"{response.reason} ({response.data})"
            )
        return loads(response.data)

    @property
    def token(self) -> str:
        if not Config.token:
            self.authorize()
        elif Config.validity < time():
            self.refresh()
        return Config.token

    def authorize(self) -> None:
        payload = {
            "client_id": Config.client,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "playlist-modify-public",
        }
        log.info("Opening browser for authorization")
        webbrowser.open(f"{self.accounts_url}/authorize?{urlencode(payload)}")
        with HTTPServer(("", 8888), HTTPRequestHandler) as HTTPRequestHandler.server:
            log.info("Listening for authentication callback")
            HTTPRequestHandler.server.serve_forever()
        code = HTTPRequestHandler.spotify_code
        self.authenticate(code)

    def authenticate(self, code: str) -> None:
        payload = {
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
            "client_id": Config.client,
            "client_secret": Config.secret,
        }
        log.info("Authenticating client")
        response = self.client.request_encode_body(
            "POST",
            self.accounts_url + "/api/token",
            fields=payload,
            encode_multipart=False,
        )
        data = self.response(response)
        Config.update(
            token=data["access_token"],
            validity=time() + data["expires_in"],
            refresh=data["refresh_token"],
        )

    def refresh(self):
        payload = {"refresh_token": Config.refresh, "grant_type": "refresh_token"}
        keys = f"{Config.client}:{Config.secret}"
        encoded_keys = b64encode(keys.encode("ascii")).decode("ascii")
        headers = {"Authorization": f"Basic {encoded_keys}"}
        log.info("Refreshing token")
        response = self.client.request_encode_body(
            "POST",
            self.accounts_url + "/api/token",
            fields=payload,
            headers=headers,
            encode_multipart=False,
        )
        data = self.response(response)
        Config.update(token=data["access_token"], validity=time() + data["expires_in"])

    @overload
    def search(self, artist: str, title: str) -> Optional[SpotifyTrack]:
        ...

    @overload
    def search(
        self, artist: str, title: str, limit: int
    ) -> Optional[List[SpotifyTrack]]:
        ...

    def search(self, artist: str, title: str, limit: int = 1):
        q: List[str] = []
        if artist:
            q += [f"artist:{artist}"]
        if title:
            q += [f"track:{title}"]
        params = {
            "limit": limit,
            "type": "track",
            "q": " ".join(q),
        }
        headers = {"Authorization": f"Bearer {self.token}"}
        query = urlencode(params, quote_via=quote).replace("%3A", ":")
        log.debug(f"Searching for {query}")
        response = self.client.request(
            "GET", f"{self.api_url}/search?{query}", headers=headers
        )
        data = self.response(response)
        items = data["tracks"]["items"]
        if items:
            tracks = [
                SpotifyTrack(
                    uri=track["id"],
                    title=track["name"],
                    artist=track["artists"][0]["name"],
                    album=track["album"]["name"],
                )
                for track in items
            ]
            return tracks[0] if limit == 1 else tracks
        return None

    def replace(self, playlist: str, tracks: List[SpotifyTrack]) -> None:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        url = self.api_url + f"/playlists/{playlist}/tracks"
        body = {"uris": [f"spotify:track:{track.uri}" for track in tracks]}
        log.info("Updating playlist")
        response = self.client.request("PUT", url, headers=headers, body=dumps(body))
        self.response(response, 201)


class HTTPRequestHandler(BaseHTTPRequestHandler):
    server: "BaseServer"
    spotify_code: str

    def do_GET(self):
        def shutdown(server):
            server.shutdown()

        HTTPRequestHandler.spotify_code = self.path.split("=")[1]
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        Thread(target=shutdown, args=(self.server,)).start()


log = getLogger('spotify')
