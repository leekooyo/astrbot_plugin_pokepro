import asyncio
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from aiocqhttp import CQHttp

from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

from .config import PluginConfig


@dataclass
class SendResult:
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    reason: str = ""


class PokeSender:
    def __init__(self, config: PluginConfig):
        self.cfg = config
        self._lock = asyncio.Lock()
        self._send_times: deque[float] = deque()
        self._last_send = 0.0

    @staticmethod
    def _normalize_id(value: int | str | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value if value > 0 else None
        value = str(value).strip()
        if not value:
            return None
        if not value.isdigit():
            raise ValueError("ID 必须为正整数")
        result = int(value)
        return result if result > 0 else None

    @classmethod
    async def poke_func(cls, client: CQHttp, user_id: int | str, group_id: int | str | None = None):
        uid = cls._normalize_id(user_id)
        if uid is None:
            raise ValueError("user_id 不能为空或 0")
        gid = cls._normalize_id(group_id)
        if gid is not None:
            await client.group_poke(group_id=gid, user_id=uid)
        else:
            await client.friend_poke(user_id=uid)

    async def _send(self, client: CQHttp, *, target_ids: Sequence[str | int],
                    group_id: str | int | None, times: int, action: str) -> SendResult:
        if isinstance(target_ids, (str, bytes)):
            raise TypeError("target_ids 必须是 ID 列表")
        result = SendResult()
        raw_targets = list(dict.fromkeys(str(tid) for tid in target_ids))
        targets = [tid for tid in raw_targets if tid.isdigit() and int(tid) > 0]
        count = max(1, min(int(getattr(self.cfg, "poke_max_times", 5)), int(times)))
        result.skipped += (len(raw_targets) - len(targets)) * count
        max_targets = max(1, int(getattr(self.cfg, "max_targets_per_action", 50)))
        result.skipped += max(0, len(targets) - max_targets) * count
        if len(targets) > max_targets:
            result.reason = "已达到单次目标上限"
        targets = targets[:max_targets]
        if not targets:
            result.reason = "没有有效目标"
            return result
        checker = getattr(self.cfg, "action_allowed", None)
        if group_id and checker and not checker(str(group_id), action):
            result.skipped += len(targets) * count
            result.reason = "该群已禁用此动作"
            return result

        for uid in targets:
            for _ in range(count):
                if group_id and checker and not checker(str(group_id), action):
                    result.skipped += 1
                    result.reason = "该群已禁用此动作"
                    continue
                # 所有来源共用发送间隔与分钟配额。
                async with self._lock:
                    now = time.monotonic()
                    while self._send_times and now - self._send_times[0] >= 60:
                        self._send_times.popleft()
                    per_minute = max(1, int(getattr(self.cfg, "max_pokes_per_minute", 60)))
                    if len(self._send_times) >= per_minute:
                        result.skipped += 1
                        result.reason = "已达到每分钟发送上限"
                        continue
                    interval = max(0.0, float(getattr(self.cfg, "poke_interval", 0.5)))
                    delay = self._last_send + interval - now
                    if delay > 0:
                        await asyncio.sleep(delay)
                    now = time.monotonic()
                    self._last_send = now
                    self._send_times.append(now)
                    result.attempted += 1
                    try:
                        await self.poke_func(client, uid, group_id)
                        result.succeeded += 1
                    except Exception as exc:
                        result.failed += 1
                        logger.warning(f"戳一戳失败 user_id={uid}: {exc}")
        logger.info(
            "戳一戳动作 %s：成功 %s，失败 %s，跳过 %s%s",
            action, result.succeeded, result.failed, result.skipped,
            f"（{result.reason}）" if result.reason else "",
        )
        return result

    async def event_send(self, event: AiocqhttpMessageEvent, *,
                         target_ids: Sequence[str | int], times: int = 1,
                         action: str = "command") -> SendResult:
        return await self._send(event.bot, target_ids=target_ids,
                                group_id=event.get_group_id(), times=times, action=action)

    async def client_send(self, client: CQHttp, *, target_ids: Sequence[str | int],
                          group_id: str | int | None = None, times: int = 1,
                          action: str = "scheduler") -> SendResult:
        return await self._send(client, target_ids=target_ids,
                                group_id=group_id, times=times, action=action)
