# 项目文件结构说明

一个典型的 vlog 剪辑项目在 Agent 完成后会产生以下文件：

```
my-vlog-project/
│
├── footage/                        # 📹 原始素材（用户提供）
│   ├── clip_001.mp4
│   ├── clip_002.mp4
│   └── ...
│
├── analysis/                       # 📊 阶段3: 素材分析输出
│   └── clip_analysis.json          #   每条素材的视觉+音频+预处理数据
│
├── edit_plan.json                  # 🧠 阶段4: LLM叙事编排输出
├── edit_plan_fixed.json            # ✅ 阶段4.5: 语音截断修复后的版本
│
├── output/
│   ├── dashboard.html              # 📊 Dashboard 网页
│   ├── storyboard/
│   │   ├── index.html              # 🎬 分镜预览网页
│   │   └── frames/                 #   分镜关键帧
│   │
│   ├── thumbnails/                 # 🖼️ 素材缩略图 (Dashboard用)
│   │   ├── clip_001_f1.jpg         #   每条素材3帧 (首/中/尾)
│   │   ├── clip_001_f2.jpg
│   │   └── ...
│   │
│   ├── qc_frames/                  # 🔍 成品QC帧 (Dashboard用)
│   │   ├── qc_0000.jpg             #   每30秒一帧
│   │   └── ...
│   │
│   ├── segments/                   # ✂️ 裁剪后的片段
│   │   ├── seg_001.mp4
│   │   └── ...
│   │
│   ├── highlights/                 # ⭐ 片头高光蒙太奇
│   │   ├── hl_1.mp4
│   │   ├── hl_2.mp4
│   │   └── montage.mp4
│   │
│   ├── titles/                     # 🏷️ 段落标题PNG (透明RGBA)
│   │   ├── title_01.png
│   │   └── ...
│   │
│   ├── sections/                   # 📹 带标题的段落视频
│   │   ├── final_sec_01.mp4
│   │   └── ...
│   │
│   ├── bgm/                       # 🎵 BGM文件
│   │   └── bgm.mp3
│   │
│   ├── video_no_bgm.mp4           # 📹 无BGM的完整视频
│   └── final.mp4                  # 🎬 成品视频！
│
└── reference/                     # 📚 阶段2: 参考研究 (可选)
    ├── ref_video.mp4
    └── ref_analysis.md
```

## 文件说明

| 文件 | 阶段 | 说明 |
|------|------|------|
| `clip_analysis.json` | 3+3.5 | 每条素材的完整分析（画面、语音、音量、预处理建议） |
| `edit_plan.json` | 4 | LLM 输出的叙事编排方案 |
| `edit_plan_fixed.json` | 4.5 | 语音截断自动修复后的方案 |
| `dashboard.html` | 4+ | 素材总览 + 成品QC 的交互式网页 |
| `storyboard/index.html` | 4+ | 分镜可视化预览网页 |
| `final.mp4` | 5 | 最终成品视频 |

## 空间占用参考

以80条素材、10分钟成品为例：
- 原始素材 footage/: ~5-15 GB
- 缩略图 thumbnails/: ~20 MB
- 片段 segments/: ~500 MB
- 成品 final.mp4: ~200-500 MB
- 总计（不含原始素材）: ~1 GB

---

*From [vlog-auto-edit](https://github.com/znyupup/ai-video-editing-skill) by nyx研究所*
