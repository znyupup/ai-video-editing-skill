---
name: vlog-auto-edit
description: AI Agent自动剪辑旅行Vlog的完整工作流。从原始素材到成品视频，系统级只需ffmpeg，其余在Python venv内完成。
version: 1.0.1
tags: [video-editing, vlog, ffmpeg, whisper, automation]
author: nyx研究所 (https://github.com/znyupup)
status: stable
---

# AI Agent 自动剪辑旅行 Vlog

> 把一堆手机拍的旅行素材，用AI自动剪成一个完整vlog。
> 最小依赖：ffmpeg + Python(whisper+Pillow) + 视觉API。系统级只装ffmpeg，其余pip在venv装。

## 触发条件

- 用户有一批旅行/日常视频素材，想自动剪成vlog
- 用户说"帮我剪个视频"、"自动剪辑"、"vlog剪辑"

## 前置要求

### 1. 系统工具

| 工具 | 用途 | 安装 |
|------|------|------|
| ffmpeg | 视频裁剪/编码/拼接/抽帧/音量检测 | `brew install ffmpeg` (macOS) / `apt install ffmpeg` (Linux) |
| Python 3.9+ | 脚本胶水 | macOS/Linux 系统自带 |

### 2. Python依赖（先检测，已有则跳过）

**先检测系统是否已安装所需包，不要无脑创建 venv：**

```bash
# 检测 whisper
python3 -c "import whisper; print('✅ whisper已安装:', whisper.__file__)"

# 检测 Pillow
python3 -c "from PIL import Image; print('✅ Pillow已安装')"
```

**⚠ 重要：不要用 `2>/dev/null` 吃掉错误！要看到实际报错才能判断是真没装还是PATH问题。**

**仅在检测不通过时才安装：**

```bash
# 方案A: 直接装到用户环境（推荐）
pip install openai-whisper Pillow

# 方案B: 如果用户环境有冲突，再用 venv
python3 -m venv .venv && source .venv/bin/activate
pip install openai-whisper Pillow
```

**⚠ 不要每个项目都新建 venv 重装一遍！whisper模型文件1.4GB，pip install也要几分钟。**

**标题卡方案自动选择：**
```bash
ffmpeg -filters 2>&1 | grep drawtext
# 有drawtext → 直接用ffmpeg，不需要Pillow
# 没有 → 用Pillow生成透明PNG再overlay（macOS brew ffmpeg通常没编freetype）
```

**可选（参考分析阶段用）：**
```bash
which yt-dlp && echo "✅ yt-dlp已安装" || pip install yt-dlp
python3 -c "import scenedetect" 2>/dev/null && echo "✅ scenedetect已安装" || pip install scenedetect
```

### 3. 视觉理解模型（API）

需要一个能理解图像内容的视觉模型API，用于分析素材画面。

**要求：**
- 支持 OpenAI Chat Completions 格式（messages + image_url）
- 支持 base64 图片输入（本地素材抽帧后编码上传）
- 中文理解能力（需要描述画面内容、标注镜头类型等）

**推荐模型：**

| 模型 | 费用 | 说明 |
|------|------|------|
| 智谱 GLM-4.6V-Flash | 免费 | 注册 https://open.bigmodel.cn 即用，中文理解好 |
| GPT-4o | 付费 | 效果最好 |
| Qwen-VL | 付费 | 阿里云，中文好 |

**调用示例：**

```python
import base64, json, urllib.request

API_URL = 'YOUR_VISION_API_ENDPOINT'   # 替换为你的视觉模型端点
API_KEY = 'YOUR_API_KEY'               # 替换为你的API Key
MODEL = 'YOUR_MODEL_NAME'             # 替换为你的模型名

with open('frame.jpg', 'rb') as f:
    img_b64 = base64.b64encode(f.read()).decode()

payload = {
    'model': MODEL,
    'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}},
        {'type': 'text', 'text': '简洁描述画面内容，标注：镜头类型(远/全/中/近/特写)、拍摄手法(固定/手持/移动)、画面氛围。格式：内容|类型|手法|氛围'}
    ]}],
    'max_tokens': 200
}

req = urllib.request.Request(API_URL, json.dumps(payload).encode(),
    {'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'})
with urllib.request.urlopen(req, timeout=30) as resp:
    result = json.loads(resp.read())
    print(result['choices'][0]['message']['content'])
```

**⚠ 视觉API调用注意事项：**
- 抽帧尺寸：缩到 720p 即可（节省上传带宽和token）
- 端点区分：有些平台视觉模型和文本模型端点不同，确认用对
- 限流：高峰时段容易被限流，加 retry + sleep

### 不需要的（踩过的坑）

- ❌ 剪映/CapCut — v10.4+ 项目文件加密，无法程序化操作
- ❌ moviepy — ffmpeg命令行已够用，多一层抽象反而不灵活
- ❌ capcut-cli (GitHub) — 基于明文JSON，对加密后的新版无效
- ❌ ImageMagick — Pillow已够用，不需要再装一个图像工具

## 工作流（7个阶段）

### 阶段1: 素材盘点

目标：了解你有什么素材。

```bash
# 批量获取素材信息
for f in footage/*.{MOV,mp4,MP4}; do
  echo "=== $f ==="
  ffprobe -v quiet -print_format json -show_format -show_streams "$f" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); \
      s=d['streams'][0]; f=d['format']; \
      print(f\"  时长: {float(f['duration']):.1f}s\"); \
      print(f\"  分辨率: {s['width']}x{s['height']}\"); \
      print(f\"  编码: {s['codec_name']}\")"
done
```

输出一份素材清单：数量、总时长、分辨率分布、拍摄时间范围。

### 阶段2: 参考研究（可选但强烈建议）

目标：建立"好vlog长什么样"的认知。不做这步直接剪，效果会很差。

**步骤：**
1. 找2-3个同类型优质vlog（B站/YouTube）
2. `yt-dlp` 下载720p视频 + 音频
3. `whisper` 转录旁白（提取叙事结构）
4. `scenedetect` 检测镜头切换（统计节奏）
5. `ffmpeg` 抽关键帧 + 视觉API分析（理解画面构成）

**已验证的规律：**

- 镜头节奏: 平均3-4秒/镜头是黄金节奏
- 内容配比: 美食40-45% + 风景30% + 人物15% + 日常15%
- 镜头类型: 近景/中景为主(60-65%)，全景/远景穿插(35-40%)
- 叙事结构: 精彩片头 → 出发/到达 → 按地点串联 → 情感升华收尾
- 长短交替: 短镜头(<2s)做蒙太奇，长镜头(>8s)做叙事

**剪辑教程要点：**
1. 找侧重点，不要流水账
2. 三幕式结构: 25%悬念 + 50%发展 + 25%收尾
3. 精彩放片头
4. 情感占51%（Walter Murch六法则）

### 阶段3: 素材三维分析

目标：让AI理解每条素材的内容。每条素材做三维分析：

**a) 音频分析 — Whisper转录**
```bash
# 提取音频（16kHz单声道WAV，whisper最佳输入）
ffmpeg -i footage/INPUT.MOV -vn -acodec pcm_s16le -ar 16000 -ac 1 /tmp/audio.wav

# Whisper转录（medium模型，中文最佳性价比）
python3 -c "
import whisper, json
model = whisper.load_model('medium')
result = model.transcribe('/tmp/audio.wav', language='zh')
for seg in result['segments']:
    print(f\"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}\")
"
```

**b) 音量检测 — ffmpeg**
```bash
ffmpeg -i footage/INPUT.MOV -af volumedetect -f null /dev/null 2>&1 | grep volume
# mean_volume: 平均音量(dB)  max_volume: 峰值音量(dB)
# mean < -40dB 基本无声  mean > -20dB 有明显声音/语音
```

**c) 视觉分析 — ffmpeg抽帧 + 视觉理解模型**
```bash
# 抽帧策略（按时长分段）
# ≤20s → 3帧(首/中/尾)
# 20-60s → 5帧
# >60s → 每15s一帧

# 抽首/中/尾三帧示例（缩到720p节省带宽）
ffmpeg -i footage/INPUT.MOV -vf "select=eq(n\,0),scale=1280:-1" -frames:v 1 -q:v 2 frame_start.jpg
ffmpeg -i footage/INPUT.MOV -vf "select=eq(n\,MIDDLE),scale=1280:-1" -frames:v 1 -q:v 2 frame_mid.jpg
ffmpeg -i footage/INPUT.MOV -vf "reverse,scale=1280:-1" -frames:v 1 -q:v 2 frame_end.jpg
```

**d) 输出格式**（每条素材一个JSON）
```json
{
  "filename": "clip_001.MOV",
  "duration": 15.3,
  "resolution": "1920x1080",
  "visual": [
    {"time": "0:00", "description": "...", "shot_type": "近景", "camera": "手持", "mood": "温馨"}
  ],
  "audio": {
    "has_speech": true,
    "mean_volume_db": -20.5,
    "max_volume_db": -3.2,
    "transcript": [{"start": 0.5, "end": 2.3, "text": "..."}]
  }
}
```

### 阶段3.5: 素材精修预处理

目标：在给LLM之前，自动标注每条素材的"推荐有效区间"，让LLM专注叙事编排。

**为什么需要这步：**
原始手机素材普遍存在：开头录制口令、同一句话重复多遍、前1-2s举手机晃动、说完话后拖很长的无意义画面。如果把这些原始数据直接给LLM，LLM输出的plan还需要逐条修补。

**预处理做四件事：**

#### a) 录制口令检测

```python
RECORDING_CUES = [
    "开始了", "好了开始", "开始录了", "好了 开始",
    "走了", "好了", "来了",  # 仅在前3s内出现时算口令
]

def detect_cues(transcript_segments, duration):
    """检测录制口令，返回skip zones"""
    skip_zones = []
    for seg in transcript_segments:
        text = seg['text'].strip()
        if seg['start'] < 3.0 and any(text.startswith(c) or text == c for c in RECORDING_CUES):
            skip_zones.append({
                'type': 'recording_cue',
                'range': [seg['start'], seg['end']],
                'text': text,
                'action': 'skip'
            })
        if seg['end'] > duration - 3.0 and text in ["好了", "走了", "好了 走"]:
            skip_zones.append({
                'type': 'recording_cue',
                'range': [seg['start'], seg['end']],
                'text': text,
                'action': 'skip'
            })
    return skip_zones
```

#### b) 重复语音检测

```python
from difflib import SequenceMatcher

def detect_repeats(segments, threshold=0.6):
    """检测重复语音，标记建议跳过的重复段"""
    repeats = []
    for i, a in enumerate(segments):
        for j, b in enumerate(segments):
            if j <= i: continue
            ratio = SequenceMatcher(None, a['text'], b['text']).ratio()
            if ratio >= threshold and len(a['text']) > 4:
                skip = a if len(a['text']) <= len(b['text']) else b
                repeats.append({
                    'type': 'repeat',
                    'range': [skip['start'], skip['end']],
                    'text': skip['text'],
                    'kept': b['text'] if skip == a else a['text'],
                    'action': 'suggest_skip'
                })
    return repeats
```

#### c) 起手晃动 / 结尾拖拽检测

```python
def detect_trim_points(segments, duration, mean_volume_db):
    """基于语音+音量推荐起止点"""
    suggested_start = 0.0
    suggested_end = duration

    if segments:
        first_speech = segments[0]['start']
        last_speech_end = segments[-1]['end']
        if first_speech > 2.0:
            suggested_start = max(0, first_speech - 0.5)
        if duration - last_speech_end > 3.0:
            suggested_end = last_speech_end + 1.5
    else:
        if duration > 5.0:
            suggested_start = 1.0

    return suggested_start, suggested_end
```

#### d) 纯画面时长限制

| 模式     | 纯画面上限 | 口令处理 | 重复处理       | 起手晃动 |
|----------|-----------|---------|---------------|---------| 
| strict   | 8-10s     | 全部去除 | 只留1遍        | 去1.5s  |
| normal   | 12-15s    | 去除明确口令 | 去明显重复   | 去1.0s  |
| loose    | 20-25s    | 仅去"开始了" | 保留大部分    | 去0.5s  |

#### e) 输出格式

预处理结果追加到素材分析数据里：

```
━━━ clip_012.mp4 | 时长25.8s | 1920x1080 ━━━
  【画面】...
  【语音】...
  【精修建议】模式: normal
    原始区间: [0.0 - 25.8]
    推荐区间: [2.4 - 25.8]
    ⊘ [0.0-2.4] 跳过: 录制口令 "开始了"
    有效语音: [2.62-25.8]
```

**⚠ 重要原则：预处理只做标注和建议，不做硬裁剪。LLM保留最终决定权。**

### 阶段4: LLM叙事编排

目标：把预处理后的素材数据交给LLM，生成剪辑方案。

输入：素材分析 + 精修建议(推荐区间) + 参考研究结论
输出：剪辑方案JSON（结构见下方schema）

#### edit_plan JSON Schema

```json
{
  "title": "视频标题",
  "structure": [
    {
      "section": "段落名 — 副标题",
      "description": "本段落内容概述",
      "clips": [
        {
          "file": "素材文件名.mp4",
          "start": 0.0,
          "end": 12.0,
          "note": "画面内容简述",
          "subtitle": "保留的语音文字"
        }
      ]
    }
  ],
  "bgm_suggestion": "BGM风格建议（含genre/mood/instruments/tempo/bpm）",
  "editing_notes": "整体剪辑说明"
}
```

**约束：**
- 同一素材可出现在多个clip中（不同时间区间）
- start/end 不能截断语音中间（阶段4.5会校验）
- 第一个section建议是"开篇"类引入段落
- 最后一个section建议是"收尾"类段落

详细prompt模板见 `templates/edit_plan_prompt.md`。

### 阶段4+ : 分镜可视化 + Dashboard（浏览器预览）

目标：把LLM输出的剪辑方案做成图文并茂的网页，方便用户直观Review。

**Dashboard 包含两个面板：**

1. **📋 素材总览** — 素材缩略图网格 + 时长/语音/音量标注 + 筛选(全部/已用/未用/含语音) + 点击查看详情
2. **✅ 成品质量检查** — 成品视频定时抽帧(每30秒) + 段落定位 + 点击放大

**使用 `gen_dashboard.py` 脚本：**

```bash
# 最小用法（只生成素材面板）
python3 scripts/gen_dashboard.py \
  --analysis clip_analysis.json \
  --plan edit_plan.json \
  --footage footage/ \
  --out output/

# 完整两面板（含成品QC帧）
python3 scripts/gen_dashboard.py \
  --analysis clip_analysis.json \
  --plan edit_plan.json \
  --footage footage/ \
  --video output/final.mp4 \
  --out output/
```

**支持两种分析数据格式（自动检测）：**
- 标准格式 `clip_analysis.json`: `{filename, duration, visual: [...], audio: {...}}`
- 紧凑格式 `clips_compact.json`: `{file, dur, visual: "string", speech: [...]}`

用户确认分镜方案后，再进入渲染阶段。

### 阶段4.5: 语音截断校验

目标：自动校验LLM输出的plan，确保没有把任何语音从中间截断。

```python
def validate_speech(plan_clips, speech_data):
    """检查每个clip的start/end是否截断了语音"""
    issues = []
    for clip in plan_clips:
        f = clip['file']
        cs, ce = clip['start'], clip['end']
        if f not in speech_data: continue
        for ss, se, txt in speech_data[f]:
            if ss < ce and se > cs:  # 语音与clip有交集
                if ss < cs - 0.3:    # 语音开始在clip之前
                    issues.append(f"截断开头: {f} clip从{cs}开始，但语音\"{txt}\"从{ss}开始")
                if se > ce + 0.5:    # 语音结束在clip之后
                    issues.append(f"截断结尾: {f} clip在{ce}结束，但语音\"{txt}\"到{se}结束")
    return issues
```

**校验不通过时：自动修复start/end，不需要回LLM重新编排。**

#### 自动修复逻辑

```python
def fix_speech_cuts(plan, speech_data, margin=0.3):
    """
    自动修复语音截断问题。直接修改plan中的start/end。
    
    参数:
        plan: edit_plan dict (会被原地修改)
        speech_data: dict, {filename: [(start, end, text), ...]}
        margin: float, 语音边界容差(秒)
    
    返回:
        fixes: list of str, 修复日志
    """
    fixes = []
    
    for sec in plan["structure"]:
        for clip in sec["clips"]:
            f = clip["file"]
            cs = float(clip["start"])
            ce = float(clip["end"])
            
            if f not in speech_data:
                continue
            
            for ss, se, txt in speech_data[f]:
                if ss >= ce or se <= cs:
                    continue
                
                # 开头截断：clip.start > speech.start + margin
                if ss < cs - margin and se > cs:
                    old_start = cs
                    new_start = max(0, ss - 0.1)
                    clip["start"] = round(new_start, 1)
                    fixes.append(
                        f"  修复开头: {f} [{old_start}→{new_start}] "
                        f"语音\"{txt[:20]}\"从{ss}s开始"
                    )
                    cs = new_start
                
                # 结尾截断：clip.end < speech.end - margin
                if se > ce + margin and ss < ce:
                    old_end = ce
                    new_end = se + 0.2
                    clip["end"] = round(new_end, 1)
                    fixes.append(
                        f"  修复结尾: {f} [{old_end}→{new_end}] "
                        f"语音\"{txt[:20]}\"到{se}s结束"
                    )
                    ce = new_end
    
    return fixes
```

**修复策略：**

| 截断类型 | 检测条件 | 修复方式 |
|----------|---------|---------| 
| 开头截断 | clip.start > speech.start + margin | clip.start → speech.start - 0.1s |
| 结尾截断 | clip.end < speech.end - margin | clip.end → speech.end + 0.2s |

**边界容差 (margin=0.3s)：** Whisper时间戳有±0.2-0.3s误差。修复后必须跑二次校验。

### 阶段5: ffmpeg自动执行

目标：把剪辑方案转成ffmpeg命令并执行。

#### 渲染策略：逐片段裁剪 → 拼接

```bash
# 单个片段裁剪+编码
ffmpeg -y -ss 00:00:02.400 -i footage/INPUT.mp4 -t 00:00:23.400 \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1" \
  -r 30 -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -ar 44100 -ac 2 \
  -movflags +faststart segments/seg_001.mp4

# 拼接成品
ffmpeg -y -f concat -safe 0 -i concat.txt -c copy -movflags +faststart output.mp4
```

#### 片头高光蒙太奇

从各段落选最有视觉冲击力的镜头，快切拼接放在视频最前面。

**选片原则：**
- 每个主要段落选1个精彩画面
- 每个镜头0.5-1秒，快切节奏
- 总共6-10个镜头，总时长5-8秒
- 排除竖屏素材
- 不加音频（-an），最终由BGM覆盖

```python
import subprocess, os

highlights = [
    ('footage/clip_a.mp4',   1.5, 2.2),
    ('footage/clip_b.mp4',   2.0, 2.7),
    # ... 每个0.7秒左右
]

for i, (f, start, end) in enumerate(highlights, 1):
    dur = end - start
    cmd = f'ffmpeg -y -ss {start} -i "{f}" -t {dur} ' \
          f'-vf "scale=1920:1080:force_original_aspect_ratio=decrease,' \
          f'pad=1920:1080:(ow-iw)/2:(oh-ih)/2" ' \
          f'-c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p ' \
          f'-an highlights/hl_{i}.mp4'
    subprocess.run(cmd, shell=True)

# concat
with open('highlights/concat.txt', 'w') as f:
    for i in range(1, len(highlights)+1):
        f.write(f"file 'hl_{i}.mp4'\n")

subprocess.run('ffmpeg -y -f concat -safe 0 -i highlights/concat.txt '
               '-c copy highlights/montage.mp4', shell=True)
```

#### 段落标题叠加

用 Pillow 生成透明RGBA的PNG，ffmpeg overlay到视频画面上。**不要用黑底标题卡**。

```python
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080
title = "段落标题"

img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 字体：macOS用冬青黑体，Linux用Noto Sans CJK
# font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 60)  # macOS
# font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 60)  # Linux
font = ImageFont.truetype("YOUR_FONT_PATH", 60)

bbox = draw.textbbox((0, 0), title, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
x, y = (W - tw) // 2, (H - th) // 2

# 柔和阴影
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
sd.text((x+2, y+2), title, fill=(0, 0, 0, 180), font=font)
shadow = shadow.filter(ImageFilter.GaussianBlur(radius=6))

img = Image.alpha_composite(img, shadow)
draw = ImageDraw.Draw(img)
draw.text((x, y), title, fill=(255, 255, 255, 240), font=font)
img.save("title_overlay.png")
```

**overlay到视频上：**

```bash
# 标题显示前3秒
ffmpeg -y -i section.mp4 -i title.png \
  -filter_complex "overlay=0:0:enable='between(t,0,3)'" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -movflags +faststart \
  section_titled.mp4
```

**⚠ overlay关键Pitfall：**
- ❌ 不要加 `shortest=1` — PNG只有1帧，会导致视频流立刻截断
- ✅ 直接用 `overlay=0:0:enable='between(t,0,3)'` 最简单可靠
- ✅ 先用短片段(5-8s)验证overlay效果

#### 段落拼接（推荐方案）

**✅ 正确方案：逐段编码 → concat copy**

```bash
echo "file 'final_sec_01.mp4'" > concat.txt
echo "file 'final_sec_02.mp4'" >> concat.txt
ffmpeg -y -f concat -safe 0 -i concat.txt -c copy -movflags +faststart output.mp4
```

**❌ 不要用xfade链式合并：** 链式xfade会导致帧数累积丢失，后半段全黑。

**段落间过渡**：段落内硬切即可。如需渐变，每段首尾加fade比xfade更可靠。

#### BGM生成与混音（可选）

BGM 可以手动添加，也可以用 AI 音乐生成工具（如 MiniMax music、Suno 等）。

##### a) AI 生成 BGM

**风格映射参考（vlog常用）：**

| Vlog 风格 | genre | mood | instruments | tempo |
|-----------|-------|------|-------------|-------|
| 轻松日常 | indie pop | cheerful, carefree | ukulele, acoustic guitar | moderate |
| 文艺治愈 | folk, acoustic | warm, gentle | acoustic guitar, piano, strings | slow |
| 美食探店 | jazz, bossa nova | cozy, playful | piano, upright bass | moderate |
| 冰雪/冬季 | cinematic, ambient | serene, majestic | piano, celesta, strings | slow |
| 热带/海岛 | tropical house | sunny, relaxed | steel drums, marimba | upbeat |
| 城市探索 | lo-fi hip hop | chill, urban | keys, vinyl crackle | moderate |

##### b) 混合到视频

```bash
# BGM 音量 10-15%（有语音的vlog要压低BGM）
ffmpeg -y -i video_no_bgm.mp4 -i bgm.m4a \
  -filter_complex "[0:a]volume=1.0[orig];[1:a]volume=0.12[bgm];[orig][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]" \
  -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k \
  -movflags +faststart output/final.mp4
```

**BGM 音量建议：**
- 有大量语音/旁白 → 8-12%
- 语音较少，空镜为主 → 15-25%
- 纯空镜蒙太奇段落 → 30-40%

## Pitfalls

1. **剪映不可用** — v10.4+ 对 draft_info.json 加密，不要浪费时间
2. **视觉API端点要区分** — 有些平台视觉模型和文本模型端点不同，确认用对
3. **Whisper模型选择** — base中文太差，large太慢，medium是性价比最优
4. **不要跳过参考研究** — 没有"好vlog标准"的AI会剪出流水账
5. **ffmpeg编码兼容** — 拼接时注意素材编码一致性，先逐片段统一编码再concat
6. **视觉API限流** — 高峰时段容易限流，加retry和sleep
7. **预处理在LLM之前做** — 口令/重复/晃动检测在阶段3.5处理
8. **预处理是建议不是硬裁剪** — LLM保留覆盖权，某些口令可能有叙事价值
9. **语音截断必须自动校验** — LLM输出的plan可能在语音中间切断
10. **Whisper幻觉** — 纯音乐/环境音段落whisper会编造文字，需用音量阈值(-40dB)过滤
11. **竖屏混横屏** — 素材分析阶段就要检测，竖屏(9:16)混在横屏里很突兀，建议去掉
12. **overlay不要加shortest=1** — PNG只有1帧，shortest=1会让视频流截断
13. **标题卡风格** — 白字+柔和阴影叠在视频画面上，**不要黑底标题卡**
14. **ffmpeg drawtext不可用** — macOS Homebrew ffmpeg默认没编译freetype，用Pillow生成PNG overlay代替
15. **HEVC警告可忽略** — "Error constructing the frame RPS" 是HEVC解码警告，不影响输出
16. **Non-monotonic DTS** — concat拼接时常见的时间戳警告，播放不受影响
17. **空镜不宜过长** — 无语音的纯画面>6s偏长，建议压缩到5-8s
18. **xfade链式合并不可靠** — 链式xfade会导致帧数累积丢失，后半段全黑，用concat代替
19. **先用短片段验证** — 每次改渲染方案都先用5-8秒短片段验证效果
20. **渲染完必须验证帧数** — `ffmpeg -i output.mp4 -f null -` 检查实际frame数
21. **BGM别太大声** — 有语音段BGM控制在8-12%，先试听再定
22. **多段BGM衔接** — 保持相近的key和tempo(bpm差值<20)
23. **混音后必须试听** — 不同素材原始音量差异大
24. **不要重复安装依赖** — whisper/Pillow等先检测再装，不要每次都新建venv

## 端到端示例

### 项目文件结构

```
my-vlog-project/
├── footage/                    # 原始素材（用户提供）
│   ├── clip_001.MOV
│   └── ...
│
├── analysis/                   # 阶段3输出
│   └── clip_analysis.json
│
├── edit_plan.json              # 阶段4输出
├── edit_plan_fixed.json        # 阶段4.5输出
│
├── output/
│   ├── dashboard.html          # Dashboard网页
│   ├── thumbnails/             # 素材缩略图
│   ├── qc_frames/              # 成品QC帧
│   ├── segments/               # 裁剪后的片段
│   ├── highlights/             # 片头高光蒙太奇
│   ├── titles/                 # 段落标题PNG
│   ├── sections/               # 带标题的段落视频
│   ├── bgm/                    # BGM文件
│   ├── video_no_bgm.mp4        # 无BGM的完整视频
│   └── final.mp4               # 🎬 成品视频
│
└── reference/                  # 阶段2输出（可选）
```

### 中间产物示例

见 `examples/` 目录下的示例文件。

### 执行流程速查

```
素材文件夹 footage/
     │
     ▼
 阶段1: 素材盘点 → ffprobe批量扫描 → 清单
     │
     ▼
 阶段2: 参考研究 → 下载优质vlog → 分析节奏（可选）
     │
     ▼
 阶段3: 素材三维分析 → whisper+音量+视觉 → clip_analysis.json
     │
     ▼
 阶段3.5: 精修预处理 → 口令/重复/晃动/纯画面标注
     │
     ▼
 阶段4: LLM叙事编排 → edit_plan.json
     │
     ▼
 阶段4+: Dashboard可视化 → 浏览器预览确认
     │
     ▼
 阶段4.5: 语音截断校验 → 自动修复
     │
     ▼
 阶段5: ffmpeg渲染 → 裁剪→标题→拼接→BGM → final.mp4 🎬
```

## 验证

- [ ] 素材盘点完成，生成清单
- [ ] 参考研究完成，提取规律
- [ ] 素材三维分析完成（视觉+音频+音量）
- [ ] 素材精修预处理完成
- [ ] LLM剪辑方案生成
- [ ] 语音截断校验通过
- [ ] ffmpeg执行成功，输出成品视频
- [ ] 成品视频质量人工确认

---

**Author:** nyx研究所 · [GitHub](https://github.com/znyupup) · [B站](https://space.bilibili.com/4330525) · 小红书 @nyx研究所
**License:** MIT
