
<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_pokepro?name=astrbot_plugin_pokepro&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_pokepro

_✨ 专业戳一戳 ✨_  

[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.0%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)
</div>

> 注意：戳一戳插件最新版依赖 `AstrBot v4.13.0+`  , 请先升级 AstrBot 至 v4.13.0+, 否则会无法加载插件

## 🤝 介绍

这是一个专业的戳一戳插件，机器人被戳时，会随机触发这些回复动作（跟戳、反戳、LLM回复、QQ表情、表情包、禁言、触发命令），也支持命令调用、关键词触发、定时戳。所有触发概率、回复内容均可自定义，开箱即用！

## 📦 安装

在 AstrBot 插件市场搜索 `astrbot_plugin_pokepro`，点击安装即可。

## ⚙️ 配置说明

### 基础设置

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `on_poke` | 开关 | 被戳监听总开关，开启后监听所有戳一戳事件 | `true` |
| `poke_cd` | 整数 | 用户戳 Bot 的冷却时间（秒），防连戳 | `10` |
| `group_poke_cd` | 整数 | 群聊级被戳监听冷却时间（秒），设为 `0` 表示关闭 | `2` |
| `follow_prob` | 小数 | 检测到别人被戳时，跟着戳一下的概率 | `0.1` |

### 回复动作配置（按权重随机触发）

所有回复动作都有 `weight`（触发权重），概率 = 本权重 / 所有权重之和。

#### 1. 反戳 (antipoke)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `max_times` | 整数 | 最大反戳次数（随机 1~N 次） | `5` |

#### 2. LLM 回复 (llm)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `template` | 文本 | LLM 提示模板，可用 `{username}` 变量 | `" {username} 戳了你一下..."` |

#### 3. QQ 表情回复 (face)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `pool` | 列表 | 表情 ID 池，随机选用 | `[1, 11, 14...]` |
| `max_copy_count` | 整数 | 最大复制数（随机发 1~N 个相同表情） | `3` |

#### 4. 表情包回复 (meme)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `pool` | 文件 | 本地表情包图片池 | `[]` |

#### 5. 禁言 (ban)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `duration` | 整数 | 基础禁言时间（秒） | `60` |
| `delta` | 整数 | 禁言时间波动范围（±秒） | `30` |
| `ban_template` | 文本 | 禁言成功时的 LLM 提示模板 | - |
| `ban_fail_template` | 文本 | 禁言失败时的 LLM 提示模板 | - |

#### 6. 触发命令 (command)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `pool` | 列表 | 命令池，随机触发一个（如"拍"、"吃"、"滚"等） | 见配置 |

### 主动戳设置

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `poke_max_times` | 整数 | 单个目标每次动作的最大戳数，所有来源均受限 | `5` |
| `poke_interval` | 小数 | 发戳间隔（秒），防风控 | `0.5` |
| `poke_keywords` | 列表 | 消息含这些关键词时自动戳几下 | `[笨蛋, 人机, 机器人, bot]` |
| `max_targets_per_action` | 整数 | 每次动作最多处理的目标数 | `50` |
| `max_pokes_per_minute` | 整数 | 所有来源共用的每分钟发送上限；超出部分跳过 | `60` |
| `allow_group_broadcast` | 开关 | 允许管理员使用“戳全体成员”，默认关闭 | `false` |
| `broadcast_max_targets` | 整数 | 一次群发最多抽取的群成员数 | `50` |
| `group_disabled_actions` | 列表 | 按群禁用动作，格式 `群号:ban,follow` | `[]` |

`group_disabled_actions` 可填 `all`、`response`、`follow`、`antipoke`、`llm`、`face`、`meme`、`record`、`ban`、`scheduler`、`broadcast`、`command`、`tool`、`keyword`。多条规则可针对不同群填写。插件还会在群内动作发送前读取 gatekeeper 的群策略；群处于 `mute`/`llm`、临时禁言或手动关闭本插件时，停止发送。

### 定时戳 (scheduler)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `enabled` | 开关 | 是否启用定时戳 | `true` |
| `cron` | 文本 | Cron 表达式（分 时 日 月 周） | `"30 22 * * *"` |
| `target` | 列表 | 发戳目标，格式 `群号:QQ号` 或 `群号:random`；随机目标排除机器人自己 | `["460973561:1959676873"]` |
| `times` | 整数 | 每次戳几下，仍受 `poke_max_times` 限制 | `1` |

## ⌨️ 命令表

| 命令 | 说明 |
|:----:|:-----|
| （被戳） | 被动触发：随机执行反戳/LLM/表情/表情包/禁言/命令 |
| `戳 @XXX [次数]` | 戳指定人；次数受 `poke_max_times` 限制 |
| `戳我` | 戳你自己 |
| `戳全体成员` | 仅管理员可用，需先开启群发开关；随机抽取不超过配置上限的人数 |

单独输入 `戳` 会显示用法，不会根据群消息历史自动选择目标。命令会回报成功、失败和跳过次数；定时任务会在日志中记录结果。`llm.weight=0` 时，禁言动作也不会额外调用 LLM 生成提示。

## 👥 贡献指南

- 🌟 **Star 这个项目！**（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码

## 📌 注意事项

- 想第一时间得到反馈可以来作者的插件反馈群（QQ群）：**460973561**（不点 star 不给进）
