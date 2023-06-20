from io import BytesIO
from typing import Union
from PIL import Image
from nonebot.adapters.onebot.v11 import MessageSegment

from ..api import osu_api, get_map_bg
from ..file import download_osu, re_map, map_path


async def get_bg(mapid: Union[str, int]) -> Union[str, MessageSegment]:
    info = await osu_api('map', map_id=mapid)
    if not info:
        return '未查询到该地图'
    elif isinstance(info, str):
        return info
    setid: int = info['beatmapset_id']
    osu = map_path / str(setid) / f"{mapid}.osu"
    if not osu.exists():
        await download_osu(setid, mapid)
    cover = re_map(osu)
    cover_path = map_path / cover
    if not cover_path.exists():
        bg = await get_map_bg(setid, cover)
        with open(cover_path, 'wb') as f:
            f.write(bg.getvalue())
    img = Image.open(cover_path)
    byt = BytesIO()
    img.save(byt, 'png')
    msg = MessageSegment.image(byt)
    return msg
