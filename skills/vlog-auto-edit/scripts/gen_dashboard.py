#!/usr/bin/env python3
"""
通用 Vlog 剪辑 Dashboard 生成器

Author: nyx研究所 (https://github.com/znyupup)
Part of: https://github.com/znyupup/ai-video-editing-skill

从 clip_analysis.json + edit_plan.json 生成暗色主题的可交互 HTML Dashboard。
两个面板:
  1. 📋 素材总览 — 缩略图网格、筛选、时长分布、点击查看详情
  2. ✅ 成品质量检查 — 成品视频定时抽帧、段落定位、点击放大

用法:
    python3 gen_dashboard.py \
        --analysis analysis/clip_analysis.json \
        --plan edit_plan.json \
        --footage footage/ \
        --out output/ \
        [--video output/final.mp4] \
        [--skip-thumbs] \
        [--skip-qc] \
        [--qc-interval 30]

依赖: ffmpeg (抽帧), Python 3.9+ (标准库即可)
"""
import json, subprocess, os, sys, argparse, html as html_mod
from pathlib import Path


# ── 辅助函数 ──────────────────────────────────────────

def fmt_time(seconds):
    """秒 → m:ss 格式"""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def get_base(filename):
    """从文件名提取base名(去扩展名)"""
    return Path(filename).stem


def run_ffmpeg(args, quiet=True):
    """执行 ffmpeg 命令"""
    cmd = ["ffmpeg", "-y"] + args
    kw = {"capture_output": True} if quiet else {}
    return subprocess.run(cmd, **kw)


# ── 数据加载与交叉匹配 ──────────────────────────────────

def load_data(analysis_path, plan_path):
    """加载素材分析数据和 edit_plan.json，交叉匹配生成 dashboard 数据。

    支持两种分析数据格式:
    - 标准格式 (clip_analysis.json): {"filename", "duration", "visual": [...], "audio": {...}}
    - 紧凑格式 (clips_compact.json): {"file", "dur", "visual": "string", "speech": [...]}
    自动检测格式。
    """

    with open(analysis_path, encoding="utf-8") as f:
        raw_analysis = json.load(f)

    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)

    # 自动检测格式
    sample = raw_analysis[0] if raw_analysis else {}
    is_compact = "file" in sample and "filename" not in sample

    # 构建 plan 中每条素材的使用信息
    usage_map = {}  # filename → [{"section", "start", "end", "note"}, ...]
    for sec in plan.get("structure", []):
        sec_name = sec.get("section", "")
        for clip in sec.get("clips", []):
            fname = clip["file"]
            if fname not in usage_map:
                usage_map[fname] = []
            usage_map[fname].append({
                "section": sec_name.split("—")[0].strip() if "—" in sec_name else sec_name,
                "start": float(clip["start"]),
                "end": float(clip["end"]),
                "note": clip.get("note", ""),
            })

    # 构建 dashboard clips 数据
    clips = []
    for item in raw_analysis:
        if is_compact:
            # 紧凑格式: {file, dur, visual(string), speech(array of strings)}
            fname = item["file"]
            dur = float(item.get("dur", 0))
            visual_str = item.get("visual", "")
            speech_lines = item.get("speech", [])
            has_speech = len(speech_lines) > 0
        else:
            # 标准格式: {filename, duration, visual(array), audio{...}}
            fname = item["filename"]
            dur = float(item.get("duration", 0))

            # 视觉描述：取第一帧的 description + shot_type/camera/mood
            visual_parts = []
            for v in item.get("visual", []):
                desc = v.get("description", "")
                extras = []
                if v.get("shot_type"):
                    extras.append(v["shot_type"])
                if v.get("camera"):
                    extras.append(v["camera"])
                if v.get("mood"):
                    extras.append(v["mood"])
                tag = "/".join(extras)
                visual_parts.append(f"{desc} [{tag}]" if tag else desc)
            visual_str = visual_parts[0] if visual_parts else ""

            # 语音内容
            audio = item.get("audio", {})
            has_speech = audio.get("has_speech", False)
            transcript = audio.get("transcript", [])
            speech_lines = []
            for seg in transcript:
                t = int(float(seg.get("start", 0)))
                text = seg.get("text", "").strip()
                if text:
                    speech_lines.append(f"[{t}s] {text}")

        base = get_base(fname)

        # 使用情况
        usages = usage_map.get(fname, [])
        is_used = len(usages) > 0
        used_dur = sum(u["end"] - u["start"] for u in usages)
        usage_ratio = round((used_dur / dur) * 100, 1) if dur > 0 else 0

        clips.append({
            "file": fname,
            "base": base,
            "dur": round(dur, 1),
            "visual": visual_str,
            "speech": speech_lines,
            "has_speech": has_speech,
            "is_used": is_used,
            "usage": usages,
            "used_dur": round(used_dur, 1),
            "usage_ratio": usage_ratio,
        })

    # 构建 sections 数据（用于 QC 面板段落定位）
    sections = []
    for sec in plan.get("structure", []):
        sec_clips = []
        for clip in sec.get("clips", []):
            sec_clips.append({
                "file": clip["file"],
                "start": float(clip["start"]),
                "end": float(clip["end"]),
            })
        sections.append({
            "name": sec.get("section", ""),
            "clips": sec_clips,
        })

    return clips, sections, plan


# ── 缩略图抽取 ──────────────────────────────────────────

def extract_thumbnails(clips_data, footage_dir, thumb_dir):
    """从每条素材抽取3帧缩略图 (首/中/尾, 480px宽)"""
    os.makedirs(thumb_dir, exist_ok=True)
    total = len(clips_data)

    for i, c in enumerate(clips_data, 1):
        fname = c["file"]
        base = c["base"]
        dur = c["dur"]
        src = os.path.join(footage_dir, fname)

        if not os.path.exists(src):
            print(f"  ⚠ [{i}/{total}] 素材不存在: {src}", file=sys.stderr)
            continue

        # 3个时间点：开头1s, 中间, 结尾前1s
        times = [
            min(1.0, dur * 0.1),
            dur / 2,
            max(0, dur - 1.0),
        ]

        all_exist = all(
            os.path.exists(os.path.join(thumb_dir, f"{base}_f{n}.jpg"))
            for n in range(1, 4)
        )
        if all_exist:
            continue

        for n, t in enumerate(times, 1):
            out_path = os.path.join(thumb_dir, f"{base}_f{n}.jpg")
            if os.path.exists(out_path):
                continue
            run_ffmpeg([
                "-ss", f"{t:.1f}", "-i", src,
                "-vframes", "1", "-q:v", "3",
                "-vf", "scale=480:-1",
                out_path,
            ])

        status = "✓" if os.path.exists(os.path.join(thumb_dir, f"{base}_f1.jpg")) else "✗"
        print(f"  {status} [{i}/{total}] {fname}")


# ── QC 帧抽取 ──────────────────────────────────────────

def extract_qc_frames(video_path, qc_dir, interval=30):
    """从成品视频每隔 interval 秒抽取1帧"""
    os.makedirs(qc_dir, exist_ok=True)

    if not os.path.exists(video_path):
        print(f"  ⚠ 成品视频不存在: {video_path}", file=sys.stderr)
        return []

    # 获取视频时长
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
        capture_output=True, text=True,
    )
    try:
        info = json.loads(probe.stdout)
        total_dur = float(info["format"]["duration"])
    except (json.JSONDecodeError, KeyError):
        print("  ⚠ 无法获取视频时长", file=sys.stderr)
        return []

    frames = []
    t = 0
    idx = 0
    while t < total_dur:
        out_path = os.path.join(qc_dir, f"qc_{idx:04d}.jpg")
        if not os.path.exists(out_path):
            run_ffmpeg([
                "-ss", f"{t:.1f}", "-i", video_path,
                "-vframes", "1", "-q:v", "2",
                "-vf", "scale=640:-1",
                out_path,
            ])
        if os.path.exists(out_path):
            frames.append({
                "file": f"qc_frames/qc_{idx:04d}.jpg",
                "time": fmt_time(t),
                "seconds": t,
            })
            print(f"  ✓ qc_{idx:04d}.jpg @ {fmt_time(t)}")
        idx += 1
        t += interval

    return frames


# ── HTML 生成 ──────────────────────────────────────────

def generate_html(clips_data, sections, plan, qc_frames, out_dir, video_info=None):
    """生成暗色主题 Dashboard HTML"""

    title = plan.get("title", "Vlog Dashboard")
    safe_title = html_mod.escape(title)

    # 统计数据
    total_clips = len(clips_data)
    total_dur = sum(c["dur"] for c in clips_data)
    used_clips = sum(1 for c in clips_data if c["is_used"])
    unused_clips = total_clips - used_clips
    speech_clips = sum(1 for c in clips_data if c["has_speech"])
    used_dur = sum(c["used_dur"] for c in clips_data)

    # QC 统计
    qc_count = len(qc_frames)
    section_count = len(sections)

    # 视频信息（成品）
    vi = video_info or {}
    final_dur_str = vi.get("duration_str", "—")
    final_size_str = vi.get("size_str", "—")
    final_codec = vi.get("codec", "—")
    final_version = vi.get("version", "")

    # 嵌入数据
    dashboard_data = {
        "clips": clips_data,
        "sections": [{"name": s["name"], "clips": s["clips"]} for s in sections],
        "qc_frames": qc_frames,
    }
    data_json = json.dumps(dashboard_data, ensure_ascii=False, separators=(",", ":"))

    # ── CSS ──
    css = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #0a0e17; color: #e0e6f0; }

/* Nav */
.nav { position: sticky; top: 0; z-index: 100; background: rgba(10,14,23,0.95); backdrop-filter: blur(12px); border-bottom: 1px solid #1e293b; padding: 12px 24px; display: flex; gap: 8px; align-items: center; }
.nav-title { font-size: 18px; font-weight: 700; color: #60a5fa; margin-right: 24px; }
.nav-btn { padding: 8px 18px; border-radius: 8px; border: 1px solid #334155; background: transparent; color: #94a3b8; cursor: pointer; font-size: 14px; transition: all 0.2s; }
.nav-btn:hover { border-color: #60a5fa; color: #e0e6f0; }
.nav-btn.active { background: #1e3a5f; border-color: #60a5fa; color: #60a5fa; font-weight: 600; }

.panel { display: none; padding: 24px; max-width: 1400px; margin: 0 auto; }
.panel.active { display: block; }

/* Stats bar */
.stats-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 28px; }
.stat-card { background: linear-gradient(135deg, #1a1f2e, #151a28); border: 1px solid #1e293b; border-radius: 12px; padding: 16px 20px; text-align: center; }
.stat-value { font-size: 28px; font-weight: 800; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.stat-label { font-size: 12px; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }

/* Filter */
.filter-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-btn { padding: 6px 14px; border-radius: 20px; border: 1px solid #334155; background: transparent; color: #94a3b8; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.filter-btn:hover { border-color: #60a5fa; }
.filter-btn.active { background: #60a5fa; border-color: #60a5fa; color: #fff; }

/* Clip Grid */
.clip-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.clip-card { position: relative; border-radius: 10px; overflow: hidden; border: 2px solid transparent; transition: all 0.3s; cursor: pointer; background: #111827; }
.clip-card:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(96,165,250,0.15); }
.clip-card.used { border-color: #22c55e30; }
.clip-card.unused { border-color: #ef444430; }
.clip-card.selected { border-color: #60a5fa !important; box-shadow: 0 0 20px rgba(96,165,250,0.3); }
.clip-thumb { width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; }
.clip-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(transparent 40%, rgba(0,0,0,0.85)); pointer-events: none; }
.clip-info { position: absolute; bottom: 0; left: 0; right: 0; padding: 8px 10px; }
.clip-name { font-size: 12px; font-weight: 600; color: #fff; }
.clip-dur { font-size: 11px; color: #94a3b8; }
.clip-badges { position: absolute; top: 6px; right: 6px; display: flex; gap: 4px; }
.badge { padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 600; }
.badge-used { background: #22c55e; color: #fff; }
.badge-unused { background: #ef4444; color: #fff; }
.badge-speech { background: #f59e0b; color: #000; }

/* Detail panel */
.clip-detail { background: #111827; border: 1px solid #1e293b; border-radius: 12px; padding: 20px; margin-top: 20px; display: none; }
.clip-detail.show { display: block; }
.clip-detail h3 { color: #60a5fa; margin-bottom: 12px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.detail-thumbs { display: flex; gap: 8px; }
.detail-thumbs img { width: 150px; border-radius: 6px; cursor: pointer; }
.detail-info-block { font-size: 14px; line-height: 1.8; }
.detail-info-block .label { color: #64748b; font-size: 12px; }
.usage-tag { display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 12px; margin: 2px; }

/* Duration bar chart */
.dur-chart { display: flex; align-items: flex-end; gap: 2px; height: 120px; margin: 20px 0; padding: 0 4px; }
.dur-bar { flex: 1; border-radius: 3px 3px 0 0; min-width: 4px; transition: all 0.3s; cursor: pointer; position: relative; }
.dur-bar:hover { opacity: 0.8; }
.dur-bar .bar-tooltip { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); background: #1e293b; padding: 6px 10px; border-radius: 6px; font-size: 11px; white-space: nowrap; z-index: 10; border: 1px solid #334155; margin-bottom: 4px; }
.dur-bar:hover .bar-tooltip { display: block; }

/* QC Panel */
.qc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.qc-card { background: #111827; border: 1px solid #1e293b; border-radius: 10px; overflow: hidden; transition: all 0.3s; cursor: pointer; }
.qc-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }
.qc-thumb { width: 100%; aspect-ratio: 16/9; object-fit: cover; }
.qc-info { padding: 10px 14px; }
.qc-time { font-size: 14px; font-weight: 600; color: #60a5fa; }
.qc-section { font-size: 12px; color: #94a3b8; margin-top: 2px; }

.qc-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.qc-stat { background: #111827; border: 1px solid #1e293b; border-radius: 10px; padding: 16px; }
.qc-stat-title { font-size: 12px; color: #64748b; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 1px; }
.qc-stat-value { font-size: 20px; font-weight: 700; color: #e0e6f0; }
.qc-stat-sub { font-size: 12px; color: #94a3b8; margin-top: 4px; }

/* Lightbox */
.lightbox { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.9); z-index: 200; justify-content: center; align-items: center; }
.lightbox.show { display: flex; }
.lightbox img { max-width: 90vw; max-height: 85vh; border-radius: 8px; }
.lightbox-close { position: absolute; top: 20px; right: 30px; font-size: 30px; color: #fff; cursor: pointer; }
.lightbox-info { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); color: #fff; font-size: 14px; background: rgba(0,0,0,0.6); padding: 8px 16px; border-radius: 8px; }

/* Section headers */
h2 { font-size: 20px; color: #f0f4ff; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #1e293b; }
h2 span { font-size: 13px; font-weight: 400; color: #64748b; margin-left: 8px; }

/* Empty state */
.empty-state { text-align: center; padding: 60px 20px; color: #64748b; }
.empty-state .icon { font-size: 48px; margin-bottom: 16px; }
.empty-state p { font-size: 14px; }

@media (max-width: 768px) {
  .detail-grid { grid-template-columns: 1fr; }
  .detail-thumbs { flex-wrap: wrap; }
  .detail-thumbs img { width: 120px; }
  .nav { flex-wrap: wrap; }
}
"""

    # ── HTML 模板 ──
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title} — 剪辑仪表盘</title>
<style>{css}</style>
</head>
<body>

<div class="nav">
  <div class="nav-title">🎬 {safe_title}</div>
  <button class="nav-btn active" onclick="showPanel(0)">📋 素材总览</button>
  <button class="nav-btn" onclick="showPanel(1)">✅ 成品质量检查</button>
</div>

<!-- ==================== PANEL 1: 素材总览 ==================== -->
<div class="panel active" id="panel-0">
  <div class="stats-bar">
    <div class="stat-card"><div class="stat-value">{total_clips}</div><div class="stat-label">总素材数</div></div>
    <div class="stat-card"><div class="stat-value">{total_dur/60:.1f}min</div><div class="stat-label">素材总时长</div></div>
    <div class="stat-card"><div class="stat-value">{used_clips}</div><div class="stat-label">已使用</div></div>
    <div class="stat-card"><div class="stat-value">{unused_clips}</div><div class="stat-label">未使用</div></div>
    <div class="stat-card"><div class="stat-value">{speech_clips}</div><div class="stat-label">含语音</div></div>
    <div class="stat-card"><div class="stat-value">{used_dur/60:.1f}min</div><div class="stat-label">使用时长</div></div>
  </div>

  <h2>时长分布 <span>每根柱子代表一条素材</span></h2>
  <div class="dur-chart" id="dur-chart"></div>

  <h2>素材库 <span>点击查看详情</span></h2>
  <div class="filter-bar">
    <button class="filter-btn active" onclick="filterClips('all')">全部 ({total_clips})</button>
    <button class="filter-btn" onclick="filterClips('used')">✅ 已使用 ({used_clips})</button>
    <button class="filter-btn" onclick="filterClips('unused')">❌ 未使用 ({unused_clips})</button>
    <button class="filter-btn" onclick="filterClips('speech')">🎙 含语音 ({speech_clips})</button>
  </div>
  <div class="clip-grid" id="clip-grid"></div>
  <div class="clip-detail" id="clip-detail"></div>
</div>

<!-- ==================== PANEL 2: 成品质量检查 ==================== -->
<div class="panel" id="panel-1">
  <div class="qc-stats">
    <div class="qc-stat">
      <div class="qc-stat-title">成品时长</div>
      <div class="qc-stat-value">{final_dur_str}</div>
      <div class="qc-stat-sub">{final_version}</div>
    </div>
    <div class="qc-stat">
      <div class="qc-stat-title">文件大小</div>
      <div class="qc-stat-value">{final_size_str}</div>
      <div class="qc-stat-sub">{final_codec}</div>
    </div>
    <div class="qc-stat">
      <div class="qc-stat-title">检查帧数</div>
      <div class="qc-stat-value">{qc_count}帧</div>
      <div class="qc-stat-sub">每30秒一帧</div>
    </div>
    <div class="qc-stat">
      <div class="qc-stat-title">段落数</div>
      <div class="qc-stat-value">{section_count}</div>
      <div class="qc-stat-sub">含段落标题overlay+BGM</div>
    </div>
  </div>

  <h2>定时抽帧预览 <span>每30秒截取一帧 · 点击放大</span></h2>
  <div class="qc-grid" id="qc-grid"></div>
  {"" if qc_frames else '<div class="empty-state"><div class="icon">🎬</div><p>暂无QC帧。请指定 --video 参数提供成品视频路径。</p></div>'}
</div>

<!-- Lightbox -->
<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <span class="lightbox-close">&times;</span>
  <img id="lightbox-img" src="">
  <div class="lightbox-info" id="lightbox-info"></div>
</div>

<script>
const DATA = {data_json};

const SECTION_COLORS = [
  '#3b82f6','#22c55e','#f59e0b','#ef4444','#a855f7',
  '#06b6d4','#ec4899','#84cc16','#f97316','#6366f1',
  '#14b8a6','#e11d48','#eab308'
];

// Panel switching
function showPanel(idx) {{
  document.querySelectorAll('.panel').forEach((p,i) => {{
    p.classList.toggle('active', i === idx);
  }});
  document.querySelectorAll('.nav-btn').forEach((b,i) => {{
    b.classList.toggle('active', i === idx);
  }});
}}

// ===== PANEL 1: Footage Gallery =====
function renderDurChart() {{
  const chart = document.getElementById('dur-chart');
  const maxDur = Math.max(...DATA.clips.map(c => c.dur));
  chart.innerHTML = DATA.clips.map((c, i) => {{
    const h = Math.max(4, (c.dur / maxDur) * 110);
    const color = c.is_used ? '#22c55e' : '#ef4444';
    return '<div class="dur-bar" style="height:'+h+'px;background:'+color+'" onclick="selectClip('+i+')"><div class="bar-tooltip">'+c.file+'<br>'+c.dur.toFixed(1)+'s'+(c.is_used?' ✅':' ❌')+'</div></div>';
  }}).join('');
}}

function makeSVGPlaceholder(text) {{
  return "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180"><rect fill="#111827" width="320" height="180"/><text x="50%" y="50%" fill="#64748b" text-anchor="middle" dy=".3em" font-size="14">' + text + '</text></svg>');
}}

function renderClipGrid(filter) {{
  const grid = document.getElementById('clip-grid');
  grid.innerHTML = DATA.clips.filter(c => {{
    if (filter === 'used') return c.is_used;
    if (filter === 'unused') return !c.is_used;
    if (filter === 'speech') return c.has_speech;
    return true;
  }}).map((c) => {{
    const idx = DATA.clips.indexOf(c);
    const thumbPath = 'thumbnails/' + c.base + '_f1.jpg';
    const placeholder = makeSVGPlaceholder(c.base);
    return '<div class="clip-card '+(c.is_used?'used':'unused')+'" id="clip-'+idx+'" onclick="selectClip('+idx+')">' +
      '<img class="clip-thumb" src="'+thumbPath+'" onerror="this.src=\\''+placeholder+'\\'">' +
      '<div class="clip-overlay"></div>' +
      '<div class="clip-badges">' +
        (c.is_used ? '<span class="badge badge-used">已用</span>' : '<span class="badge badge-unused">弃用</span>') +
        (c.has_speech ? '<span class="badge badge-speech">🎙</span>' : '') +
      '</div>' +
      '<div class="clip-info"><div class="clip-name">'+c.file+'</div><div class="clip-dur">'+c.dur.toFixed(1)+'s</div></div>' +
    '</div>';
  }}).join('');
}}

let currentFilter = 'all';
function filterClips(f) {{
  currentFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  renderClipGrid(f);
}}

function selectClip(idx) {{
  const c = DATA.clips[idx];
  document.querySelectorAll('.clip-card').forEach(el => el.classList.remove('selected'));
  const el = document.getElementById('clip-'+idx);
  if (el) el.classList.add('selected');

  const detail = document.getElementById('clip-detail');
  detail.classList.add('show');

  const thumbs = [1,2,3].map(n => {{
    const p = 'thumbnails/' + c.base + '_f' + n + '.jpg';
    return '<img src="'+p+'" onerror="this.style.display=\\'none\\'" onclick="openLightbox(\\''+p+'\\', \\''+c.file+' — 帧'+n+'\\')">';
  }}).join('');

  let usageHtml = '';
  if (c.usage.length > 0) {{
    usageHtml = c.usage.map(u =>
      '<div class="usage-tag" style="background:#22c55e20;border:1px solid #22c55e40">📎 ' + u.section + ' [' + u.start + 's→' + u.end + 's] ' + u.note + '</div>'
    ).join('');
  }} else {{
    usageHtml = '<span style="color:#ef4444">未在成品中使用</span>';
  }}

  let speechHtml = '';
  if (c.speech.length > 0) {{
    speechHtml = c.speech.map(s => '<div style="color:#f59e0b;font-size:13px">💬 ' + s + '</div>').join('');
  }}

  detail.innerHTML = '<h3>📹 ' + c.file + '</h3>' +
    '<div class="detail-grid">' +
      '<div><div class="detail-thumbs">' + thumbs + '</div></div>' +
      '<div class="detail-info-block">' +
        '<div><span class="label">时长：</span>' + c.dur.toFixed(1) + '秒</div>' +
        '<div><span class="label">画面：</span>' + c.visual + '</div>' +
        (speechHtml ? '<div style="margin-top:8px"><span class="label">语音内容：</span>' + speechHtml + '</div>' : '') +
        '<div style="margin-top:8px"><span class="label">使用情况：</span><div>' + usageHtml + '</div></div>' +
        (c.is_used ? '<div><span class="label">使用比例：</span><span style="color:#22c55e;font-weight:700">' + c.usage_ratio + '%</span> (' + c.used_dur + 's / ' + c.dur.toFixed(1) + 's)</div>' : '') +
      '</div>' +
    '</div>';

  detail.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
}}

// ===== PANEL 2: QC =====
function renderQC() {{
  const grid = document.getElementById('qc-grid');
  if (!DATA.qc_frames || DATA.qc_frames.length === 0) return;

  function getSection(seconds) {{
    let acc = 0;
    for (const sec of DATA.sections) {{
      const secDur = sec.clips.reduce((s,c) => s + (c.end - c.start), 0);
      if (seconds < acc + secDur) return sec.name;
      acc += secDur;
    }}
    return '—';
  }}

  grid.innerHTML = DATA.qc_frames.map((f, i) => {{
    const section = getSection(f.seconds);
    const sectionShort = section.length > 20 ? section.substring(0, 18) + '…' : section;
    const placeholder = makeSVGPlaceholder('Frame ' + (i+1));
    return '<div class="qc-card" onclick="openLightbox(\\''+f.file+'\\', \\''+f.time+' — '+section.replace(/'/g,"\\\\'")+'\\')">' +
      '<img class="qc-thumb" src="'+f.file+'" onerror="this.src=\\''+placeholder+'\\'">' +
      '<div class="qc-info">' +
        '<div class="qc-time">⏱ ' + f.time + '</div>' +
        '<div class="qc-section">≈ ' + sectionShort + '</div>' +
      '</div>' +
    '</div>';
  }}).join('');
}}

// Lightbox
function openLightbox(src, info) {{
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lightbox-info').textContent = info;
  document.getElementById('lightbox').classList.add('show');
}}
function closeLightbox() {{
  document.getElementById('lightbox').classList.remove('show');
}}
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeLightbox(); }});

// Init
renderDurChart();
renderClipGrid('all');
renderQC();
</script>
</body>
</html>"""

    html_path = os.path.join(out_dir, "dashboard.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)

    return html_path


# ── 成品视频信息 ──────────────────────────────────────────

def get_video_info(video_path):
    """获取成品视频的基本信息"""
    if not video_path or not os.path.exists(video_path):
        return None

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", video_path],
        capture_output=True, text=True,
    )
    try:
        info = json.loads(probe.stdout)
        fmt = info.get("format", {})
        dur = float(fmt.get("duration", 0))
        size = int(fmt.get("size", 0))

        # 找视频流的编码
        codec = "—"
        for s in info.get("streams", []):
            if s.get("codec_type") == "video":
                codec = s.get("codec_name", "—").upper()
                break

        return {
            "duration_str": fmt_time(dur),
            "size_str": f"{size / (1024**3):.2f} GB" if size > 1024**3 else f"{size / (1024**2):.0f} MB",
            "codec": f"{codec}编码",
            "version": "",
        }
    except (json.JSONDecodeError, KeyError):
        return None


# ── 主入口 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="通用 Vlog 剪辑 Dashboard 生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 只生成素材面板（无QC帧）
  python3 gen_dashboard.py --analysis analysis/clip_analysis.json --plan edit_plan.json --footage footage/ --out output/

  # 完整两面板（含成品QC）
  python3 gen_dashboard.py --analysis analysis/clip_analysis.json --plan edit_plan.json --footage footage/ --video output/final.mp4 --out output/

  # 跳过缩略图抽取（使用已有的）
  python3 gen_dashboard.py --analysis analysis/clip_analysis.json --plan edit_plan.json --footage footage/ --out output/ --skip-thumbs
""",
    )
    parser.add_argument("--analysis", required=True, help="clip_analysis.json 路径")
    parser.add_argument("--plan", required=True, help="edit_plan.json 路径")
    parser.add_argument("--footage", required=True, help="素材文件夹路径")
    parser.add_argument("--out", default="output", help="输出目录 (默认: output)")
    parser.add_argument("--video", default=None, help="成品视频路径（用于QC抽帧）")
    parser.add_argument("--skip-thumbs", action="store_true", help="跳过缩略图抽取")
    parser.add_argument("--skip-qc", action="store_true", help="跳过QC帧抽取")
    parser.add_argument("--qc-interval", type=int, default=30, help="QC帧间隔秒数 (默认: 30)")
    args = parser.parse_args()

    out_dir = args.out
    thumb_dir = os.path.join(out_dir, "thumbnails")
    qc_dir = os.path.join(out_dir, "qc_frames")
    os.makedirs(out_dir, exist_ok=True)

    # Step 1: 加载数据
    print("Step 1: 加载分析数据...")
    clips_data, sections, plan = load_data(args.analysis, args.plan)
    total = len(clips_data)
    used = sum(1 for c in clips_data if c["is_used"])
    print(f"  ✓ {total} 条素材, {used} 条已使用, {len(sections)} 个段落")

    # Step 2: 抽取缩略图
    if not args.skip_thumbs:
        print(f"\nStep 2: 抽取缩略图 → {thumb_dir}")
        extract_thumbnails(clips_data, args.footage, thumb_dir)
    else:
        print("\nStep 2: 跳过缩略图抽取")

    # Step 3: 抽取QC帧
    qc_frames = []
    video_info = None
    if args.video and not args.skip_qc:
        print(f"\nStep 3: 抽取QC帧 → {qc_dir}")
        video_info = get_video_info(args.video)
        qc_frames = extract_qc_frames(args.video, qc_dir, args.qc_interval)
        print(f"  ✓ {len(qc_frames)} 帧")
    elif args.video:
        # 有视频但跳过QC，仍读已有帧
        print("\nStep 3: 跳过QC帧抽取，使用已有帧")
        video_info = get_video_info(args.video)
        # 扫描已有 QC 帧
        if os.path.isdir(qc_dir):
            idx = 0
            while True:
                fpath = os.path.join(qc_dir, f"qc_{idx:04d}.jpg")
                if not os.path.exists(fpath):
                    break
                qc_frames.append({
                    "file": f"qc_frames/qc_{idx:04d}.jpg",
                    "time": fmt_time(idx * args.qc_interval),
                    "seconds": idx * args.qc_interval,
                })
                idx += 1
        print(f"  ✓ 找到 {len(qc_frames)} 帧")
    else:
        print("\nStep 3: 未指定成品视频，跳过QC面板")

    # Step 4: 生成 HTML
    print("\nStep 4: 生成 Dashboard HTML...")
    html_path = generate_html(clips_data, sections, plan, qc_frames, out_dir, video_info)
    print(f"  ✓ {html_path}")

    # 统计
    file_size = os.path.getsize(html_path)
    print(f"\n{'='*50}")
    print(f"✅ Dashboard 生成完成!")
    print(f"   文件: {html_path}")
    print(f"   大小: {file_size / 1024:.0f} KB")
    print(f"   素材: {total} 条 ({used} 已用 / {total - used} 未用)")
    if qc_frames:
        print(f"   QC帧: {len(qc_frames)} 帧")

    # macOS 自动打开
    if sys.platform == "darwin":
        subprocess.run(["open", html_path])


if __name__ == "__main__":
    main()
