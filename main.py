from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .core.config import PluginConfig
from .core.on_poke import GetPokeHandler
from .core.scheduler import PokeScheduler
from .core.send_poke import PokeSender
from .core.utils import get_ats, get_member_ids


class PokeproPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = PluginConfig(config, context)
        self.sender = PokeSender(self.cfg)
        self.get_poke_handler = GetPokeHandler(context, self.cfg, self.sender)
        self.scheduler = None

    def _normalize_poke_times(self, times: int | str | None) -> int:
        try:
            value = int(times) if times is not None else 1
        except (TypeError, ValueError):
            value = 1
        return max(1, min(self.cfg.poke_max_times, value))

    async def initialize(self):
        if self.cfg.scheduler.enabled:
            self.scheduler = PokeScheduler(self.cfg, self.sender)
            self.scheduler.start()

    async def terminate(self):
        if self.scheduler:
            self.scheduler.shutdown()

    @filter.command("戳", alias={"戳我", "戳全体成员"})
    async def on_poke_cmd(self, event: AiocqhttpMessageEvent):
        """戳 @某人/我/全体成员"""
        msg = event.message_str.strip()
        parts = msg.split()
        end = parts[-1] if parts else ""
        times = self._normalize_poke_times(end if end.isdigit() else 1)

        is_admin = event.is_admin()
        gid = event.get_group_id()
        self_id = event.get_self_id()

        # 获取目标用户ID
        broadcast = "全体成员" in msg
        if broadcast:
            if not gid:
                yield event.plain_result("戳全体成员仅群聊可用。")
                return
            if not is_admin:
                yield event.plain_result("戳全体成员仅管理员可用。")
                return
            if not self.cfg.allow_group_broadcast:
                yield event.plain_result("群发戳未启用，请先在插件配置中开启。")
                return
            target_ids = [str(mid) for mid in await get_member_ids(
                event, num=self.cfg.broadcast_max_targets
            )]
            action = "broadcast"
        else:
            target_ids: list[str] = get_ats(event, skip_first_seg=False)
            if msg.startswith("戳我") or "我" in parts[1:]:
                target_ids.append(event.get_sender_id())
            if not target_ids and not gid:
                target_ids.append(event.get_sender_id())
            action = "command"

        target_ids = list(dict.fromkeys(
            tid for tid in target_ids if tid.isdigit() and tid != self_id
        ))
        if not target_ids:
            yield event.plain_result("用法：/戳 @群友 [次数]；戳自己用 /戳我 [次数]，群发用 /戳全体成员。")
            return

        result = await self.sender.event_send(
            event,
            target_ids=target_ids,
            times=times,
            action=action,
        )
        event.stop_event()
        yield event.plain_result(
            f"戳一戳：成功 {result.succeeded}，失败 {result.failed}，跳过 {result.skipped}"
            + (f"（{result.reason}）" if result.reason else "")
        )

    @filter.llm_tool()
    async def llm_poke_user(
        self,
        event: AiocqhttpMessageEvent,
        user_id: str,
        times: int = 1,
    ):
        """
        戳指定用户。
        Args:
            user_id(string): 要戳的目标用户QQ号，必定为一串数字，如(12345678)
            times(number): 戳的次数，默认为1，实际会限制在插件配置允许的最大次数内
        """
        user_id = str(user_id).strip()
        if not user_id or not user_id.isdigit():
            return "戳一戳失败：user_id 必须是纯数字 QQ 号"

        if user_id == event.get_self_id():
            return "戳一戳失败：不能戳机器人自己"

        actual_times = self._normalize_poke_times(times)

        try:
            result = await self.sender.event_send(
                event,
                target_ids=[user_id],
                times=actual_times,
                action="tool",
            )
            return (
                f"戳用户 {user_id}：成功 {result.succeeded}，失败 {result.failed}，"
                f"跳过 {result.skipped}"
                + (f"（{result.reason}）" if result.reason else "")
            )
        except Exception as e:
            return f"戳一戳失败：{e}"

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AiocqhttpMessageEvent):
        """监听消息"""
        # 设置定时器用的客户端
        if self.scheduler:
            self.scheduler.set_client(event.bot, event.get_self_id())

        # 收到自己被戳的事件
        if self.cfg.on_poke:
            async for msg in self.get_poke_handler.handle(event):
                yield msg

        # 关键字触发戳一戳
        if event.is_at_or_wake_command and self.cfg.poke_keywords:
            if self.cfg.hit_poke_keywords(event.message_str):
                await self.sender.event_send(
                    event,
                    target_ids=[event.get_sender_id()],
                    times=1,
                    action="keyword",
                )
