from starlite import Request, Starlite, post
from starlite.middleware.session.server_side import ServerSideSessionConfig
from starlite.storage.memory import MemoryStorage
from starlite.testing import AsyncTestClient

session_config = ServerSideSessionConfig(storage=MemoryStorage())


@post(path="/test")
def set_session_data(request: Request) -> None:
    request.session["foo"] = "bar"


app = Starlite(route_handlers=[set_session_data], middleware=[session_config.middleware])


async def test_set_session_data() -> None:
    async with AsyncTestClient(app=app, session_config=session_config) as client:
        await client.post("/test")
        assert await client.get_session_data() == {"foo": "bar"}
