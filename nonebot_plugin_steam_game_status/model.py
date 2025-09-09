import json
from typing import Any, List, TypedDict
from nonebot.internal.driver import Response, HeaderTypes, ContentTypes

class GroupData(TypedDict):
    status: bool
    user_list: List[str]

class GroupData2(GroupData):
    adapter: str
    
class GroupData3(GroupData2):
    xijiayi: bool
    

class UserData(TypedDict):
    time: int
    game_name: str
    nickname: str

class SafeResponse:
    def __init__(self, response: Response):
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code
    
    @property
    def headers(self) -> "HeaderTypes":
        return self._response.headers
    
    @property
    def content(self) -> "ContentTypes":
        return self._response.content
    
    @property
    def request(self) -> Any:
        return self._response.request
    
    def __repr__(self) -> str:
        return f"SafeResponse({self._response})"
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)
    
    @property
    def text(self) -> str:
        if self._response.content is None:
            return ""
        elif isinstance(self._response.content, str):
            return self._response.content
        elif isinstance(self._response.content, bytes):
            try:
                return self._response.content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    return self._response.content.decode('latin-1')
                except UnicodeDecodeError:
                    return self._response.content.decode('utf-8', errors='replace')
        else:
            return str(self._response.content)
    
    def json(self) -> dict:
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            raise ValueError(f"Response is not valid JSON: {self.text[:100]}...")
    
