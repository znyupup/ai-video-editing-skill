#!/usr/bin/env python3
"""
分镜可视化网页生成器

Author: nyx研究所 (https://github.com/znyupup)
Part of: https://github.com/znyupup/ai-video-editing-skill

从 edit_plan JSON 提取关键帧，生成暗色主题的分镜预览网页。
用于 LLM 编排后给用户直观 Review。

用法:
    python3 gen_storyboard.py --plan edit_plan.json --footage footage/ --out output/storyboard/

依赖: ffmpeg (抽帧), Python 3.9+ (标准库即可)
"""
import json, subprocess, os, html, argparse, sys


# ── 配色 ──────────────────────────────────────────────
COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
    "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
    "#F8C471", "#82E0AA", "#F1948A", "#AED6F1", "#D2B4DE",
]


def extract_frames(plan, footage_dir, frames_dir):
    """从每个clip的中间时刻抽取关键帧"""
    os.makedirs(frames_dir, exist_ok=True)
    frame_map = {}
    clip_idx = 0

    for sec in plan["structure"]:
        for c in sec["clips"]:
            clip_idx += 1
            fname = c["file"]
            start = float(c["start"])
            end = float(c["end"])
            mid = (start + end) / 2

            frame_path = os.path.join(frames_dir, f"frame_{clip_idx:03d}.jpg")
            frame_map[clip_idx] = frame_path

            if os.path.exists(frame_path):
                continue

            src = os.path.join(footage_dir, fname)
            if not os.path.exists(src):
                print(f"  ⚠ 素材不存在: {src}", file=sys.stderr)
                continue

            cmd = [
                "ffmpeg", "-y", "-ss", f"{mid:.1f}", "-i", src,
                "-vframes", "1", "-q:v", "3",
                "-vf", "scale=480:-1",
                frame_path,
            ]
            subprocess.run(cmd, capture_output=True)
            status = "✓" if os.path.exists(frame_path) else "✗"
            print(f"  {status} frame_{clip_idx:03d}: {fname} @{mid:.1f}s")

    return frame_map, clip_idx


def generate_html(plan, frames_dir, out_dir, total_clips):
    """生成分镜可视化HTML"""
    clips_html = []
    timeline_html = []
    clip_idx = 0
    total_dur = 0

    # 计算总时长
    for sec in plan["structure"]:
        sec_dur = sum(float(c["end"]) - float(c["start"]) for c in sec["clips"])
        total_dur += sec_dur

    if total_dur == 0:
        total_dur = 1  # 防除零

    # 生成段落和卡片
    for si, sec in enumerate(plan["structure"]):
        color = COLORS[si % len(COLORS)]
        sec_name = sec["section"]
        sec_desc = sec.get("description", "")
        sec_dur = sum(float(c["end"]) - float(c["start"]) for c in sec["clips"])
        pct = (sec_dur / total_dur) * 100

        # 时间线段
        tl_label = sec_name.split("—")[0].strip() if "—" in sec_name else sec_name
        if len(tl_label) > 6:
            tl_label = tl_label[:5] + "…"
        timeline_html.append(
            f'<div class="tl-seg" style="width:{pct}%;background:{color}" '
            f'title="{html.escape(sec_name)} ({sec_dur:.0f}s)">{html.escape(tl_label)}</div>'
        )

        # 段落头
        clips_html.append(f'''
    <div class="section-header" style="border-left-color: {color}">
      <div class="section-num">段落 {si+1}</div>
      <h2>{html.escape(sec_name)}</h2>
      <div class="section-desc">{html.escape(sec_desc)}</div>
      <div class="section-meta">{len(sec["clips"])} 个片段 · {sec_dur:.0f}秒</div>
    </div>
    <div class="clips-grid">
        ''')

        # 片段卡片
        for c in sec["clips"]:
            clip_idx += 1
            fname = c["file"]
            start = float(c["start"])
            end = float(c["end"])
            dur = end - start
            note = c.get("note", "")
            subtitle = c.get("subtitle", "")
            frame_file = f"frames/frame_{clip_idx:03d}.jpg"
            has_frame = os.path.exists(os.path.join(frames_dir, f"frame_{clip_idx:03d}.jpg"))

            img_tag = (
                f'<img src="{frame_file}" alt="{html.escape(fname)}" loading="lazy">'
                if has_frame
                else '<div class="no-frame">无帧</div>'
            )

            subtitle_html = ""
            if subtitle:
                subtitle_html = f'<div class="clip-subtitle">💬 {html.escape(subtitle[:80])}</div>'

            clips_html.append(f'''
      <div class="clip-card">
        <div class="clip-frame">{img_tag}</div>
        <div class="clip-info">
          <div class="clip-file">{html.escape(fname)}</div>
          <div class="clip-time">
            <span class="time-badge">{start:.1f}s → {end:.1f}s</span>
            <span class="dur-badge">{dur:.1f}s</span>
          </div>
          <div class="clip-note">{html.escape(note)}</div>
          {subtitle_html}
        </div>
      </div>
            ''')

        clips_html.append("</div>")

    # 组装完整页面
    title = html.escape(plan.get("title", "Vlog 分镜方案"))
    bgm = html.escape(plan.get("bgm_suggestion", ""))
    notes = html.escape(plan.get("editing_notes", ""))

    bgm_html = f'<div class="meta-note">🎵 BGM建议: {bgm}</div>' if bgm else ""
    notes_html = f'<div class="meta-note">📝 {notes}</div>' if notes else ""

    page = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>分镜方案 — {title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
  background: #0f0f0f; color: #e0e0e0; line-height: 1.6;
}}
.header {{
  background: linear-gradient(135deg, #1a1a2e, #16213e);
  padding: 40px 32px 30px;
  border-bottom: 1px solid #333;
}}
.header h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 8px; }}
.header .meta {{ color: #888; font-size: 14px; }}
.header .meta span {{ margin-right: 20px; }}
.meta-note {{ color: #999; font-size: 13px; margin-top: 8px; }}
.stats {{
  display: flex; gap: 32px; margin-top: 14px;
}}
.stat-item {{ text-align: center; }}
.stat-val {{ font-size: 26px; font-weight: 700; color: #fff; }}
.stat-label {{ font-size: 12px; color: #666; }}
.timeline {{
  display: flex; height: 32px; margin: 20px 32px 0;
  border-radius: 6px; overflow: hidden;
}}
.tl-seg {{
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; color: #000; font-weight: 600;
  min-width: 20px; cursor: default; transition: filter 0.2s;
}}
.tl-seg:hover {{ filter: brightness(1.2); }}
.container {{ padding: 20px 32px 60px; max-width: 1400px; margin: 0 auto; }}
.section-header {{
  margin-top: 36px; margin-bottom: 16px;
  padding: 12px 20px; border-left: 4px solid;
  background: #1a1a1a; border-radius: 0 8px 8px 0;
}}
.section-num {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; }}
.section-header h2 {{ font-size: 20px; font-weight: 600; margin: 2px 0; }}
.section-desc {{ font-size: 13px; color: #999; margin-top: 2px; }}
.section-meta {{ font-size: 13px; color: #666; margin-top: 4px; }}
.clips-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}}
.clip-card {{
  background: #1a1a1a; border-radius: 10px;
  overflow: hidden; transition: transform 0.2s, box-shadow 0.2s;
  border: 1px solid #2a2a2a;
}}
.clip-card:hover {{
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  border-color: #444;
}}
.clip-frame {{ position: relative; aspect-ratio: 16/9; overflow: hidden; background: #111; }}
.clip-frame img {{ width: 100%; height: 100%; object-fit: cover; }}
.no-frame {{ display:flex; align-items:center; justify-content:center; height:100%; color:#555; }}
.clip-info {{ padding: 12px 14px; }}
.clip-file {{ font-size: 12px; color: #888; font-family: "SF Mono", "Fira Code", monospace; margin-bottom: 6px; }}
.clip-time {{ display: flex; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }}
.time-badge {{
  background: #2a2a3a; color: #7eb8da; padding: 2px 8px;
  border-radius: 4px; font-size: 12px; font-family: monospace;
}}
.dur-badge {{
  background: #2a3a2a; color: #7eda7e; padding: 2px 8px;
  border-radius: 4px; font-size: 12px; font-family: monospace;
}}
.clip-note {{ font-size: 13px; color: #aaa; line-height: 1.5; }}
.clip-subtitle {{ font-size: 12px; color: #c9a96e; margin-top: 6px; line-height: 1.4; }}
</style>
</head>
<body>
<div class="header">
  <h1>🎬 {title}</h1>
  <div class="meta">
    <span>📹 {clip_idx} 个片段</span>
    <span>📂 {len(plan["structure"])} 个段落</span>
    <span>⏱ {total_dur:.0f}秒 ({total_dur/60:.1f}分钟)</span>
  </div>
  <div class="stats">
    <div class="stat-item"><div class="stat-val">{len(plan["structure"])}</div><div class="stat-label">段落</div></div>
    <div class="stat-item"><div class="stat-val">{clip_idx}</div><div class="stat-label">片段</div></div>
    <div class="stat-item"><div class="stat-val">{total_dur/60:.1f}</div><div class="stat-label">分钟</div></div>
  </div>
  {bgm_html}
  {notes_html}
</div>
<div class="timeline">
  {"".join(timeline_html)}
</div>
<div class="container">
  {"".join(clips_html)}
</div>
</body>
</html>'''

    html_path = os.path.join(out_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)

    return html_path


def main():
    parser = argparse.ArgumentParser(description="从 edit_plan 生成分镜可视化网页")
    parser.add_argument("--plan", required=True, help="edit_plan JSON 文件路径")
    parser.add_argument("--footage", required=True, help="素材文件夹路径")
    parser.add_argument("--out", default="output/storyboard", help="输出目录 (默认: output/storyboard)")
    parser.add_argument("--skip-frames", action="store_true", help="跳过关键帧抽取（使用已有帧）")
    args = parser.parse_args()

    # 加载 plan
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)

    out_dir = args.out
    frames_dir = os.path.join(out_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    # Step 1: 抽取关键帧
    if not args.skip_frames:
        print("Step 1: 抽取关键帧...")
        frame_map, total_clips = extract_frames(plan, args.footage, frames_dir)
    else:
        print("Step 1: 跳过关键帧抽取（使用已有帧）")
        total_clips = sum(len(s["clips"]) for s in plan["structure"])

    # Step 2: 生成 HTML
    print("\nStep 2: 生成HTML...")
    html_path = generate_html(plan, frames_dir, out_dir, total_clips)

    print(f"\n✅ 生成完成: {html_path}")
    print(f"   {total_clips} 个片段, {len(plan['structure'])} 个段落")

    # macOS 自动打开
    if sys.platform == "darwin":
        subprocess.run(["open", html_path])


if __name__ == "__main__":
    main()
