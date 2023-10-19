import re
from random import shuffle
from typing import Union, Type

from expiringdict import ExpiringDict
from nonebot import on_command
from nonebot.adapters.red import MessageEvent as RedMessageEvent, MessageSegment as RedMessageSegment
from nonebot.adapters.onebot.v11 import MessageEvent as v11MessageEvent, MessageSegment as v11MessageSegment
from nonebot.internal.matcher import Matcher
from nonebot.typing import T_State
from nonebot.log import logger
from nonebot_plugin_guild_patch import GuildMessageEvent

from .utils import split_msg
from ..api import get_sayo_map_info, get_recommend, update_recommend

recommend = on_command('recommend', aliases={'推荐', '推荐铺面', '推荐谱面'}, priority=11, block=True)
recommend_cache = ExpiringDict(1000, 60 * 60 * 12)


async def handle_recommend(state: T_State, matcher: Type[Matcher]):
    user = state['user']
    mode = state['mode']
    mods = state['mods']
    if mods == ['4K']:
        key_count = '4'
    elif mods == ['7K']:
        key_count = '7'
    else:
        key_count = '4,7'
    if mode == '1' or mode == '2':
        await matcher.finish('很抱歉，该模式暂不支持推荐')
    if not recommend_cache.get(user):
        recommend_cache[user] = set()
        await update_recommend(user)
    recommend_data = await get_recommend(user, mode, key_count)
    shuffle(recommend_data.data.list)
    if not recommend_data.data.list:
        await matcher.finish('没有可以推荐的图哦，自己多打打喜欢玩的图吧')
    for i in recommend_data.data.list:
        if i.id not in recommend_cache[user]:
            recommend_cache[user].add(i.id)
            recommend_map = i
            break
    else:
        await matcher.finish('今天已经没有可以推荐的图啦，明天再来吧')
        return
    bid = int(re.findall('https://osu.ppy.sh/beatmaps/(.*)', recommend_map.mapLink)[0])
    map_info = await get_sayo_map_info(bid, 1)
    sid = map_info.data.sid
    for i in map_info.data.bid_data:
        if i.bid == bid:
            bg = i.bg
            break
    else:
        bg = ''
        logger.debug(f'如果看到这句话请联系作者 有问题的是{bid}, {sid}')
    s = f'推荐的铺面是{recommend_map.mapName} ⭐{round(recommend_map.difficulty, 2)}\n{"".join(recommend_map.mod)}\n' \
        f'预计pp为{round(recommend_map.predictPP, 2)}\n提升概率为{round(recommend_map.passPercent*100, 2)}%\n' \
        f'{recommend_map.mapLink}\nhttps://kitsu.moe/api/d/{sid}\n' \
        f'https://txy1.sayobot.cn/beatmaps/download/novideo/{sid}'
    pic_url = f'https://dl.sayobot.cn/beatmaps/files/{sid}/{bg}'
    return pic_url, s


@recommend.handle(parameterless=[split_msg()])
async def _(event: Union[v11MessageEvent, GuildMessageEvent], state: T_State):
    if 'error' in state:
        await recommend.finish(v11MessageSegment.reply(event.message_id) + state['error'])
    pic_url, s = await handle_recommend(state, recommend)
    await recommend.finish(v11MessageSegment.reply(event.message_id) + v11MessageSegment.image(pic_url) + s)


@recommend.handle(parameterless=[split_msg()])
async def _(event: RedMessageEvent, state: T_State):
    if 'error' in state:
        await recommend.finish(RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) + state['error'])
    pic_url, s = await handle_recommend(state, recommend)
    await recommend.finish(RedMessageSegment.reply(event.msgSeq, event.msgId, event.senderUid) +
                           RedMessageSegment.image(pic_url) + s)
