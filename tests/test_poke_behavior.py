import asyncio
import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from astrbot_plugin_pokepro.core.config import PluginConfig
from astrbot_plugin_pokepro.core.cooldown import Cooldown
from astrbot_plugin_pokepro.core.on_poke import GetPokeHandler
from astrbot_plugin_pokepro.core.scheduler import PokeScheduler
from astrbot_plugin_pokepro.core.send_poke import PokeSender
from astrbot_plugin_pokepro.main import PokeproPlugin


class PokeBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduler_sends_one_complete_user_id(self):
        scheduler = PokeScheduler.__new__(PokeScheduler)
        scheduler.client = object()
        scheduler.target_list = [("123456", "random")]
        scheduler.plugin_cfg = SimpleNamespace(action_allowed=lambda _gid, _action: True)
        scheduler.cfg = SimpleNamespace(times=1)
        scheduler.sender = SimpleNamespace(client_send=AsyncMock(return_value=SimpleNamespace(
            succeeded=1, failed=0, skipped=0, reason=""
        )))
        scheduler._pick_random_member = AsyncMock(return_value="87654321")

        await scheduler._on_trigger()

        self.assertEqual(
            scheduler.sender.client_send.await_args.kwargs["target_ids"],
            ["87654321"],
        )

    async def test_scheduler_checks_group_policy_before_picking_member(self):
        scheduler = PokeScheduler.__new__(PokeScheduler)
        scheduler.client = object()
        scheduler.target_list = [("123456", "random")]
        scheduler.plugin_cfg = SimpleNamespace(action_allowed=lambda _gid, _action: False)
        scheduler.sender = SimpleNamespace(client_send=AsyncMock())
        scheduler._pick_random_member = AsyncMock(return_value="87654321")
        await scheduler._on_trigger()
        scheduler._pick_random_member.assert_not_awaited()
        scheduler.sender.client_send.assert_not_awaited()

    async def test_sender_reports_failed_calls(self):
        sender = PokeSender(SimpleNamespace(poke_interval=0))
        client = SimpleNamespace(group_poke=AsyncMock(side_effect=RuntimeError("failed")))

        result = await sender.client_send(
            client, target_ids=["87654321"], group_id="123456", times=1
        )

        self.assertEqual(result.attempted, 1)
        self.assertEqual(result.succeeded, 0)
        self.assertEqual(result.failed, 1)

    async def test_sender_shares_minute_quota_across_actions(self):
        cfg = SimpleNamespace(poke_interval=0, poke_max_times=3,
                              max_targets_per_action=50, max_pokes_per_minute=2)
        sender = PokeSender(cfg)
        client = SimpleNamespace(group_poke=AsyncMock())

        first = await sender.client_send(
            client, target_ids=["87654321", "87654321"], group_id="123456",
            times=2, action="scheduler"
        )
        second = await sender.client_send(
            client, target_ids=["23456789"], group_id="123456",
            times=1, action="command"
        )

        self.assertEqual((first.succeeded, second.skipped), (2, 1))
        self.assertEqual(client.group_poke.await_count, 2)

    async def test_group_rule_and_gatekeeper_policy_block_actions(self):
        rules = PluginConfig._parse_disabled_actions(SimpleNamespace(
            group_disabled_actions=["123456:ban,follow"]
        ))
        self.assertEqual(rules["123456"], {"ban", "follow"})
        cfg = SimpleNamespace(_disabled_actions=rules,
                              _gatekeeper_allows=lambda _gid: True)
        self.assertFalse(PluginConfig.action_allowed(cfg, "123456", "ban"))
        self.assertTrue(PluginConfig.action_allowed(cfg, "123456", "scheduler"))

        with tempfile.TemporaryDirectory() as temp:
            gate_dir = Path(temp) / "gatekeeper"
            gate_dir.mkdir()
            (gate_dir / "modes.json").write_text(json.dumps({
                "version": 3, "meta": {"on": True, "bans": {}},
                "groups": {"123456": {"mode": "mute", "manual_off": []}}
            }), encoding="utf-8")
            with patch("astrbot_plugin_pokepro.core.config.get_astrbot_plugin_data_path",
                       return_value=temp):
                self.assertFalse(PluginConfig._gatekeeper_allows(cfg, "123456"))

    async def test_random_target_excludes_bot(self):
        scheduler = PokeScheduler.__new__(PokeScheduler)
        scheduler.client = SimpleNamespace(get_group_member_list=AsyncMock(return_value=[
            {"user_id": 999999}, {"user_id": 87654321}
        ]))
        scheduler.self_id = "999999"
        self.assertEqual(await scheduler._pick_random_member("123456"), "87654321")

    async def test_llm_tool_reports_actual_failure(self):
        plugin = PokeproPlugin.__new__(PokeproPlugin)
        plugin.cfg = SimpleNamespace(poke_max_times=3)
        plugin.sender = SimpleNamespace(event_send=AsyncMock(return_value=SimpleNamespace(
            succeeded=0, failed=1, skipped=0, reason=""
        )))
        event = SimpleNamespace(get_self_id=lambda: "999999")
        result = await plugin.llm_poke_user(event, "87654321", 1)
        self.assertIn("失败 1", result)
        self.assertNotIn("已戳", result)

    async def test_ban_does_not_request_llm_when_weight_is_zero(self):
        handler = GetPokeHandler.__new__(GetPokeHandler)
        handler.cfg = SimpleNamespace(
            ban=SimpleNamespace(ban_template="{username}", ban_fail_template="{username}"),
            llm=SimpleNamespace(weight=0),
            action_allowed=lambda _gid, _action: True,
            get_ban_time=lambda: 60,
        )
        handler.llm = SimpleNamespace(build_prompt=AsyncMock(), get_conversation=AsyncMock())
        event = SimpleNamespace(
            bot=SimpleNamespace(set_group_ban=AsyncMock()),
            get_group_id=lambda: "123456",
            get_sender_id=lambda: "87654321",
            get_self_id=lambda: "999999",
            request_llm=lambda **_kwargs: "unexpected LLM call",
        )
        with patch("astrbot_plugin_pokepro.core.on_poke.check_ban_permission",
                   new=AsyncMock(return_value=(True, ""))):
            results = [item async for item in handler.respond_ban(event)]
        self.assertEqual(results, [None])
        event.bot.set_group_ban.assert_awaited_once()
        handler.llm.build_prompt.assert_not_awaited()

    async def test_no_target_command_does_not_poke_history(self):
        plugin = PokeproPlugin.__new__(PokeproPlugin)
        plugin.cfg = SimpleNamespace(poke_max_times=3)
        plugin.sender = SimpleNamespace(event_send=AsyncMock())
        event = SimpleNamespace(
            message_str="戳", is_admin=lambda: False,
            get_group_id=lambda: "123456", get_self_id=lambda: "999999",
            get_sender_id=lambda: "87654321", get_messages=lambda: [],
            bot=SimpleNamespace(get_group_msg_history=AsyncMock()),
            plain_result=lambda text: text,
        )
        results = [item async for item in plugin.on_poke_cmd(event)]
        self.assertTrue(any("用法" in item for item in results))
        event.bot.get_group_msg_history.assert_not_awaited()
        plugin.sender.event_send.assert_not_awaited()

    async def test_admin_broadcast_needs_opt_in_and_deduplicates_targets(self):
        plugin = PokeproPlugin.__new__(PokeproPlugin)
        plugin.cfg = SimpleNamespace(poke_max_times=3, allow_group_broadcast=False,
                                     broadcast_max_targets=50)
        plugin.sender = SimpleNamespace(event_send=AsyncMock(return_value=SimpleNamespace(
            succeeded=1, failed=0, skipped=0, reason=""
        )))
        event = SimpleNamespace(
            message_str="戳全体成员", is_admin=lambda: True,
            get_group_id=lambda: "123456", get_self_id=lambda: "999999",
            get_sender_id=lambda: "87654321", get_messages=lambda: [],
            plain_result=lambda text: text, stop_event=lambda: None,
        )
        self.assertTrue([item async for item in plugin.on_poke_cmd(event)])
        plugin.sender.event_send.assert_not_awaited()

        plugin.cfg.allow_group_broadcast = True
        with patch("astrbot_plugin_pokepro.main.get_member_ids",
                   new=AsyncMock(return_value=[999999, 87654321, 87654321])) as members:
            results = [item async for item in plugin.on_poke_cmd(event)]
        members.assert_awaited_once_with(event, num=50)
        self.assertEqual(plugin.sender.event_send.await_args.kwargs["target_ids"],
                         ["87654321"])
        self.assertTrue(any("成功 1" in item for item in results))

    async def test_non_admin_cannot_broadcast_or_fall_back_to_history(self):
        plugin = PokeproPlugin.__new__(PokeproPlugin)
        plugin.cfg = SimpleNamespace(poke_max_times=3, allow_group_broadcast=True)
        plugin.sender = SimpleNamespace(event_send=AsyncMock())
        event = SimpleNamespace(
            message_str="戳全体成员",
            is_admin=lambda: False,
            get_group_id=lambda: "123456",
            get_self_id=lambda: "999999",
            get_sender_id=lambda: "87654321",
            get_messages=lambda: [],
            bot=SimpleNamespace(get_group_msg_history=AsyncMock()),
            plain_result=lambda text: text,
        )

        results = [item async for item in plugin.on_poke_cmd(event)]

        self.assertTrue(any("管理员" in item for item in results))
        event.bot.get_group_msg_history.assert_not_awaited()
        plugin.sender.event_send.assert_not_awaited()

    async def test_unrelated_poke_does_not_consume_response_cooldown(self):
        config = SimpleNamespace(
            poke_cd=10, group_poke_cd=2, follow_prob=0,
            action_allowed=lambda _gid, _action: True,
        )
        handler = GetPokeHandler.__new__(GetPokeHandler)
        handler.cfg = config
        handler.cooldown = Cooldown(config)
        handler._modules = ["response"]
        handler._weights = [1]
        called = []

        async def respond(_event):
            called.append(True)
            yield "response"

        handler.handlers = {"response": respond}
        handler.sender = SimpleNamespace(event_send=AsyncMock())

        def event(target):
            raw = {
                "post_type": "notice", "notice_type": "notify", "sub_type": "poke",
                "self_id": 999999, "user_id": 87654321, "target_id": target,
                "group_id": 123456,
            }
            return SimpleNamespace(
                message_obj=SimpleNamespace(raw_message=raw),
                get_extra=lambda _key: False,
            )

        self.assertEqual([x async for x in handler.handle(event(11111111))], [])
        self.assertEqual([x async for x in handler.handle(event(999999))], ["response"])
        self.assertEqual(len(called), 1)


if __name__ == "__main__":
    unittest.main()
