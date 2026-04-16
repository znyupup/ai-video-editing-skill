# 🎬 Vlog Auto Edit — AI Agent 自动剪辑旅行 Vlog

> 把一堆手机拍的旅行素材，用 AI Agent 自动剪成一个完整 Vlog。
> 你只需要提供素材文件夹，剩下的交给 Agent。

**Vibe Editing** — 不用学剪辑软件，不用自己挑选素材，不用纠结叙事结构。
告诉 AI 你想要什么风格，它帮你从头到尾搞定。

🧑‍💻 by **nyx研究所** — [GitHub](https://github.com/znyupup) · [B站](https://space.bilibili.com/4330525) · [小红书](https://www.xiaohongshu.com/) @nyx研究所 · [X / Twitter](https://x.com/znyupup_music)

## ✨ 这是什么

这是一份给 AI Agent（Claude Code / Hermes / OpenClaw / GPT 等）使用的 **Skill 文件**，定义了从原始素材到成品视频的完整自动剪辑工作流。

它不是一个传统的软件程序——而是一份**指导 AI Agent 工作的知识文件**，包含：
- 完整的工作流程定义
- 每个步骤的具体命令和代码
- 24 条实战踩坑经验
- 可视化预览工具
- 模板和示例数据

## 🎯 解决什么问题

你去旅行拍了 80 个视频片段，回来之后：
- ❌ 打开剪映/PR，面对几十G素材不知从何下手
- ❌ 花了3小时挑选素材，又花3小时调整顺序
- ❌ 最后剪出来的要么是流水账，要么节奏奇怪
- ❌ 或者就这么一直放着，永远不会去剪

用了这个 Skill：
- ✅ 把素材文件夹丢给 AI Agent
- ✅ Agent 自动理解每条素材（画面、语音、音量）
- ✅ Agent 像专业剪辑师一样编排叙事结构
- ✅ 你在浏览器里预览确认
- ✅ Agent 自动渲染、加标题、配BGM，输出成品

## 🛠️ 最小依赖

系统级只需要装两样东西：

| 工具 | 用途 | 安装 |
|------|------|------|
| **ffmpeg** | 视频裁剪/编码/拼接/抽帧/混音 | `brew install ffmpeg` / `apt install ffmpeg` |
| **Python 3.9+** | 脚本胶水 | macOS/Linux 自带 |

Python 依赖（Agent 会自动检测和安装）：
- `openai-whisper` — 语音转录
- `Pillow` — 标题图片生成

还需要一个**视觉理解 API**（用来看懂画面内容）：

| 模型 | 费用 | 说明 |
|------|------|------|
| 智谱 GLM-4.6V-Flash | 免费 | 注册 [open.bigmodel.cn](https://open.bigmodel.cn) 即用，中文好 |
| GPT-4o | 付费 | 效果最好 |
| Qwen-VL | 付费 | 阿里云，中文好 |

**不需要：** 剪映 / CapCut / Premiere / moviepy / ImageMagick

## 📋 只有 4 步

```
 ┌──────────────────────────────────────────────────────────┐
 │                                                          │
 │   素材文件夹           ❶ 分析          自动，不用管      │
 │   footage/ ──────────▶ Agent 理解每条素材的画面、       │
 │                        语音、音量，标记问题片段          │
 │                                                          │
 │                        ❷ 编排          自动，不用管      │
 │                        Agent 像剪辑师一样规划            │
 │                        叙事结构和镜头节奏                │
 │                                                          │
 │                        ❸ 预览     ◀── 你看一眼          │
 │                        浏览器打开 Dashboard               │
 │                        确认方案，或提修改意见             │
 │                                                          │
 │                        ❹ 出片          自动，不用管      │
 │                        裁剪 → 加标题 → 拼接 → BGM        │
 │                                 │                        │
 │                                 ▼                        │
 │                           🎬 final.mp4                   │
 │                                                          │
 └──────────────────────────────────────────────────────────┘
```

**你唯一需要做的就是第 ❸ 步——看一眼方案，说"可以"。** 其他全是 Agent 自动完成。

### ❶ 分析 — Agent 理解你的素材

Agent 会自动对每条素材做三件事：
- **听** — Whisper 转录语音内容
- **看** — 抽帧 + 视觉 API 理解画面（内容、镜头类型、氛围）
- **量** — 检测音量，区分有语音 / 静音 / 环境音

然后自动做预处理：去掉开头的"好了开始录了"、重复说了三遍的同一句话、举手机的晃动、说完话后的拖拽。

### ❷ 编排 — Agent 像剪辑师一样规划

基于素材分析结果，Agent 会：
- 用**三幕式结构**编排叙事（开篇引入 → 主体发展 → 情感收尾）
- 控制**镜头节奏**（平均 3-4 秒/镜头，长短交替）
- 自动选最精彩的镜头做**片头蒙太奇**
- 校验语音边界，**确保不会把话切在中间**
- 建议 BGM 风格

### ❸ 预览 — 你在浏览器里确认

Agent 生成一个交互式 Dashboard 网页：

- **素材总览** — 缩略图网格，标注已用/未用/含语音，点击看详情
- **分镜预览** — 每个镜头的关键帧 + 时间线 + 段落结构

你看完说"可以"，或者说"第三段换个素材"——Agent 调整后再给你看。

### ❹ 出片 — Agent 自动渲染

- 统一编码（h264, 1080p, 30fps）
- 段落标题叠加（白字柔和阴影，不是黑底标题卡）
- 片段拼接成完整视频
- BGM 混音（有语音段自动压低 BGM）
- 输出 `final.mp4` 🎬

## 🚀 怎么用

### 快速开始

复制下面的指令发给你的 AI Agent，它会自动完成安装和配置：

```
请从 https://github.com/znyupup/ai-video-editing-skill 克隆仓库，
阅读 SKILL.md 学习完整工作流，然后帮我把 footage/ 目录下的素材剪成一个旅行vlog。
```

> 💡 一般情况下 Agent 能自行完成 ffmpeg 检测、Python 依赖安装、视觉 API 配置等所有前置步骤。你只需要准备好素材文件夹和一个视觉模型的 API Key。

### 方式一：配合 AI Agent 使用（推荐）

1. 把 `SKILL.md` 加载到你的 AI Agent
2. 告诉 Agent：`帮我把 footage/ 目录下的素材剪成一个旅行vlog`
3. 等着看 Dashboard，确认方案，收片

支持的 Agent 平台：
- [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview) — `git clone` 后 `/read SKILL.md` 加载
- [OpenClaw](https://github.com/nicepkg/openclaw) — 导入到 Skill 库
- 其他支持自定义指令/知识库的 Agent 均可使用

### 方式二：作为参考手册

即使不用 AI Agent，SKILL.md 本身也是一份详细的 ffmpeg + Whisper + 视觉 API 视频剪辑手册，可以手动按步骤执行。

## 📁 项目结构

```
vlog-auto-edit/
├── SKILL.md                    # 🧠 核心：完整工作流定义（给 AI Agent 读的）
├── README.md                   # 📖 项目介绍（给人类读的）
├── LICENSE                     # MIT
│
├── scripts/
│   ├── gen_dashboard.py        # 📊 Dashboard 生成器
│   └── gen_storyboard.py       # 🎬 分镜预览生成器
│
├── templates/
│   └── edit_plan_prompt.md     # 📝 LLM 叙事编排 prompt 模板
│
└── examples/
    ├── clip_analysis.json      # 示例：素材分析数据
    ├── edit_plan.json          # 示例：剪辑方案
    └── project_structure.md    # 示例：项目文件结构说明
```

## 🧠 进阶用法

### 参考研究

在分析素材之前，可以让 Agent 先研究 2-3 个同类型优质 vlog（B站/YouTube），提取镜头节奏和叙事结构作为参考。这一步可选，但能显著提升成品质量。

### 调整剪辑风格

编辑 `templates/edit_plan_prompt.md` 中的参数：
- 镜头节奏（平均秒数/镜头）
- 内容配比（美食/风景/人物比例）
- 叙事结构（三幕式比例）
- 目标时长

### 调整预处理严格度

Agent 在分析阶段支持三种预处理模式：
- `strict` — 激进裁剪，最短成品
- `normal` — 均衡模式（默认）
- `loose` — 保守裁剪，保留更多内容

### 自定义视觉模型

支持任何兼容 OpenAI Chat Completions 格式的视觉模型，替换 SKILL.md 中的 API 配置即可。

## ⚠️ 已知限制

- 目前针对 **旅行 Vlog** 优化，其他类型视频需调整 prompt 模板
- 需要视觉理解 API（推荐智谱免费模型）
- Whisper 转录在 CPU 上较慢（12分钟音频约3分钟）
- BGM 自动生成需要额外的音乐 API（可选，也可以手动加 BGM）
- macOS 的 Homebrew ffmpeg 通常没有 drawtext filter，Skill 中已用 Pillow 方案替代

## ⚠️ 踩坑合集

SKILL.md 中记录了 24 条实战踩坑经验，这里列几个关键的：

1. **剪映 v10.4+ 项目文件加密** — 不要尝试程序化操作剪映
2. **xfade 链式合并会丢帧** — 用 concat 代替
3. **overlay 不要加 shortest=1** — PNG 只有1帧，会截断整个视频
4. **Whisper 会幻觉** — 纯环境音会编造文字，需用音量阈值过滤
5. **先短片段验证** — 每次改渲染方案先用 5-8 秒片段试
6. **预处理是建议不是硬裁剪** — LLM 可能觉得某个"口令"很有趣要保留

完整列表见 [SKILL.md](./SKILL.md) 的 Pitfalls 章节。

## 🤝 贡献

欢迎提 Issue 和 PR！特别欢迎：
- 更多类型视频的 prompt 模板（美食探店、城市漫步、户外运动...）
- 新的视觉模型适配
- Dashboard 功能增强
- 其他 Agent 平台的适配指南

## 👤 作者

**nyx研究所** — [GitHub](https://github.com/znyupup) · [B站 @nyx研究所](https://space.bilibili.com/4330525) · 小红书 @nyx研究所 · [X / Twitter](https://x.com/znyupup_music)

## 📄 License

MIT — 随便用，标注来源就行。

## 致谢

- [ffmpeg](https://ffmpeg.org/) — 视频处理的瑞士军刀
- [OpenAI Whisper](https://github.com/openai/whisper) — 语音转录
- [智谱AI](https://open.bigmodel.cn/) — 免费视觉理解模型
