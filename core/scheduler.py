# core/scheduler.py
from __future__ import annotations

import random

from aiocqhttp import CQHttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from astrbot.api import logger

from .config import PluginConfig
from .send_poke import PokeSender


class PokeScheduler:
    """
    定时戳调度器
    """

    def __init__(self, config: PluginConfig, sender: PokeSender):
        self.plugin_cfg = config
        self.cfg = config.scheduler
        self.cron = self.cfg.cron
        self.target_list = config.target_list
        self.sender = sender

        self._scheduler = AsyncIOScheduler()
        self._started = False
        self._job_id = "scheduler_poke"

        self.client: CQHttp | None = None
        self.self_id: str = ""

    def set_client(self, client: CQHttp, self_id: str = ""):
        self.client = client
        if self_id:
            self.self_id = str(self_id)

    # ========== 生命周期 ==========

    def start(self) -> None:
        if self._started:
            return

        self._register_job()
        self._scheduler.start()
        self._started = True

    def shutdown(self) -> None:
        if not self._started:
            return

        self._scheduler.shutdown(wait=False)
        self._started = False

    def _register_job(self):
        try:
            trigger = CronTrigger.from_crontab(self.cron)
        except Exception as e:
            logger.error(f"cron 无效: {self.cron}, {e}")
            return
        self._scheduler.add_job(
            self._on_trigger,
            trigger=trigger,
            id=self._job_id,
            replace_existing=True,
        )
        logger.debug(f"已注册定时戳任务，Cron: {self.cron}")

    # [patcher:random-target] begin —— 支持 target 写成 "群号:random"，每次随机挑一个群成员
    RANDOM_TARGET_SENTINELS = {"random", "rand", "*", "随机"}

    async def _pick_random_member(self, group_id: str) -> str | None:
        """从群成员中随机挑一个，排除机器人自己。"""
        try:
            members = await self.client.get_group_member_list(
                group_id=int(group_id)
            ) or []
        except Exception as e:
            logger.error(f"定时戳：获取群 {group_id} 成员列表失败：{e}")
            return None
        self_id = self.self_id
        ids = [
            str(m.get("user_id"))
            for m in members
            if m.get("user_id") and str(m.get("user_id")) != self_id
        ]
        if not ids:
            return None
        return random.choice(ids)
    # [patcher:random-target] end

    async def _on_trigger(self) -> None:
        if not self.client:
            return
        for target in self.target_list:
            gid, uid = target
            if not self.plugin_cfg.action_allowed(gid, "scheduler"):
                logger.info("定时戳群 %s：群策略已禁用，跳过", gid)
                continue
            # [patcher:random-target] begin
            if str(uid).strip().lower() in self.RANDOM_TARGET_SENTINELS:
                uid = await self._pick_random_member(gid)
                if not uid:
                    logger.warning(f"定时戳：群 {gid} 未能取到可戳成员，已跳过")
                    continue
            # [patcher:random-target] end
            result = await self.sender.client_send(
                client=self.client,
                target_ids=[uid],
                group_id=gid,
                times=self.cfg.times,
            )
            logger.info(
                "定时戳群 %s：成功 %s，失败 %s，跳过 %s%s",
                gid, result.succeeded, result.failed, result.skipped,
                f"（{result.reason}）" if result.reason else "",
            )
