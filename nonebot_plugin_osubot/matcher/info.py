from nonebot import on_command
from nonebot_plugin_alconna import UniMessage
from nonebot.typing import T_State
from .utils import split_msg
from ..draw import draw_info
from ..utils import NGM

info = on_command("info", priority=11, block=True, aliases={"Info", "INFO"})


@info.handle(parameterless=[split_msg()])
async def _info(state: T_State):
    if "error" in state:
        await UniMessage.text(state["error"]).send(reply_to=True)
        return
    data = await draw_info(
        state["user"], NGM[state["mode"]], state["day"], state["is_name"]
    )
    if isinstance(data, str):
        await UniMessage.text(data).send(reply_to=True)
        return
    await UniMessage.image(raw=data).send(reply_to=True)
