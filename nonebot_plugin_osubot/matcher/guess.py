import asyncio
import random
from asyncio import TimerHandle
from difflib import SequenceMatcher
from typing import Dict

from expiringdict import ExpiringDict
from nonebot import on_command, on_message
from nonebot.internal.rule import Rule
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment

from ..utils import NGM
from ..api import osu_api
from ..schema import Score
from ..database.models import UserData

games: Dict[int, Score] = {}
timers: Dict[int, TimerHandle] = {}
hint_dic = {'pic': False, 'artist': False, 'creator': False, 'mode': False, 'user': False}
group_hint = {}
guess_audio = on_command('音频猜歌', priority=11, block=True)
guess_song_cache = ExpiringDict(1000, 60 * 60 * 24)
guess_user: Dict[int, UserData] = {}


async def get_random_beatmap_set(binded_id, group_id, ttl=10):
    if ttl == 0:
        return
    user = await UserData.filter(user_id=random.choice(binded_id)).first()
    bp_info = await osu_api('bp', user.osu_id, NGM[str(user.osu_mode)])
    guess_user[group_id] = user
    if isinstance(bp_info, str):
        await guess_audio.finish('发生了错误，再试试吧')
    score_ls = [Score(**i) for i in bp_info]
    selected_score = random.choice(score_ls)
    if selected_score.beatmapset.id not in guess_song_cache[group_id]:
        guess_song_cache[group_id].add(selected_score.beatmapset.id)
    else:
        return await get_random_beatmap_set(binded_id, group_id, ttl - 1)
    return selected_score


@guess_audio.handle()
async def _(event: GroupMessageEvent, bot: Bot, mather: Matcher):
    await guess_handler(event, bot, mather)


async def guess_handler(event: GroupMessageEvent, bot: Bot, mather: Matcher):
    group_id = event.group_id
    group_member = await bot.get_group_member_list(group_id=group_id)
    user_id_ls = [i['user_id'] for i in group_member]
    binded_id = await UserData.filter(user_id__in=user_id_ls).values_list('user_id', flat=True)
    if not binded_id:
        await guess_audio.finish('群里还没有人绑定osu账号呢，绑定了再来试试吧')
    if not guess_song_cache.get(group_id):
        guess_song_cache[group_id] = set()
    selected_score = await get_random_beatmap_set(binded_id, group_id)
    if not selected_score:
        await guess_audio.finish('好像没有可以猜的歌了，今天的猜歌就到此结束吧！')
    if games.get(group_id, None):
        await guess_audio.finish('现在还有进行中的猜歌呢，请等待当前猜歌结束')
    games[group_id] = selected_score
    set_timeout(mather, group_id)
    await guess_audio.send('开始音频猜歌游戏，猜猜下面音频的曲名吧')
    print(selected_score.beatmapset.title)
    await guess_audio.finish(MessageSegment.record(f'https://cdn.sayobot.cn:25225/preview/{selected_score.beatmapset.id}.mp3'))


async def stop_game(matcher: Matcher, cid: int):
    timers.pop(cid, None)
    if games.get(cid, None):
        game = games.pop(cid)
        if group_hint.get(cid, None):
            group_hint[cid] = None
        msg = f"猜歌超时，游戏结束，正确答案是{game.beatmapset.title_unicode}"
        if game.beatmapset.title_unicode != game.beatmapset.title:
            msg += f' [{game.beatmapset.title}]'
        await matcher.send(msg)


def set_timeout(matcher: Matcher, cid: int, timeout: float = 300):
    timer = timers.get(cid, None)
    if timer:
        timer.cancel()
    loop = asyncio.get_running_loop()
    timer = loop.call_later(
        timeout, lambda: asyncio.ensure_future(stop_game(matcher, cid))
    )
    timers[cid] = timer


def game_running(event: GroupMessageEvent) -> bool:
    return bool(games.get(event.group_id, None))


word_matcher = on_message(Rule(game_running), block=True, priority=12)


@word_matcher.handle()
async def _(event: GroupMessageEvent):
    song_name = games[event.group_id].beatmapset.title
    song_name_unicode = games[event.group_id].beatmapset.title_unicode
    r1 = SequenceMatcher(None, song_name.lower(), event.get_plaintext().lower()).ratio()
    r2 = SequenceMatcher(None, song_name_unicode.lower(), event.get_plaintext().lower()).ratio()
    if r1 >= 0.6 or r2 >= 0.6:
        games.pop(event.group_id)
        if group_hint.get(event.group_id, None):
            group_hint[event.group_id] = None
        msg = f"恭喜{event.sender.nickname}猜出正确答案为{song_name_unicode}"
        await word_matcher.finish(MessageSegment.reply(event.message_id) + msg)

hint = on_command('音频提示', priority=11, block=True, rule=Rule(game_running))


@hint.handle()
async def _(event: GroupMessageEvent, bot: Bot):
    score = games[event.group_id]
    if not group_hint.get(event.group_id, None):
        group_hint[event.group_id] = hint_dic.copy()
    if all(group_hint[event.group_id].values()):
        await hint.finish('已无更多提示，加油哦')
    true_keys = []
    for key, value in group_hint[event.group_id].items():
        if not value:
            true_keys.append(key)
    action = random.choice(true_keys)
    if action == 'pic':
        group_hint[event.group_id]['pic'] = True
        await hint.finish(MessageSegment.image(score.beatmapset.covers.cover))
    if action == 'artist':
        group_hint[event.group_id]['artist'] = True
        msg = f'曲师为：{score.beatmapset.artist_unicode}'
        if score.beatmapset.artist_unicode != score.beatmapset.artist:
            msg += f' [{score.beatmapset.artist}]'
        await hint.finish(msg)
    if action == 'creator':
        group_hint[event.group_id]['creator'] = True
        await hint.finish(f'谱师为：{score.beatmapset.creator}')
    if action == 'mode':
        group_hint[event.group_id]['mode'] = True
        await hint.finish(f'模式为：{score.mode}')
    if action == 'user':
        group_hint[event.group_id]['user'] = True
        group_member = await bot.get_group_member_info(group_id=event.group_id, user_id=guess_user[event.group_id].user_id)
        name = group_member.get('card', group_member['nickname'])
        await hint.finish(f'该曲为{name}的bp')
