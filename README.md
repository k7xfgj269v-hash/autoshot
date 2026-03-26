# 招工视频自动化生成工具

输入岗位信息 → AI 生成脚本/配图/配音 → Remotion 合成视频 → 可选上传快手/抖音/视频号

---

## 功能概览

| 模式 | 输入 | 流程 |
|------|------|------|
| **Mode A**（AI生成） | 岗位文字描述 | DeepSeek 生成脚本 → Qwen 生成8张配图 → edge-tts 合成配音 → Remotion 渲染视频 |
| **Mode B**（素材优化） | 原始视频 + 岗位说明 | FFmpeg 抽帧+提取音频 → Whisper 转写 → Qwen-VL 分析场景 → DeepSeek 优化脚本 → Remotion 重新合成 |

---

## 项目结构

```
recruitment-video-tool/
├── main.py             # 入口（启动 Gradio 服务）
├── start.bat           # Windows 一键启动脚本
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量模板（复制为 .env 并填入密钥）
│
├── src/                # 业务代码
│   ├── app.py          # Gradio UI
│   ├── pipeline.py     # 核心流水线逻辑
│   └── config.py       # 配置（读取环境变量）
│
├── remotion/           # Remotion React 视频渲染项目
│   ├── src/
│   │   ├── index.tsx   # Remotion 入口，注册 ModeA / ModeB
│   │   ├── ModeA.tsx   # AI配图模板（Ken Burns效果 + 字幕 + 配音）
│   │   ├── ModeB.tsx   # 素材优化模板（原视频片段拼接 + 新字幕）
│   │   └── types.ts    # 共享 TypeScript 类型定义
│   ├── package.json
│   └── remotion.config.ts
│
├── scripts/            # 平台发布自动化脚本说明
│   ├── upload-kuaishou.md
│   ├── upload-douyin.md
│   └── upload-shipinhao.md
│
├── assets/
│   ├── bgm/            # 放入免版权 BGM（.mp3），有配音时音量自动降为 10%
│   └── fonts/          # 放入字幕字体文件
│
├── uploads/            # Mode B 临时上传目录（gitignored）
├── output/             # 生成产物（gitignored）
│   ├── images/         # Qwen 生成的配图
│   ├── tts/            # edge-tts 生成的配音文件
│   └── videos/         # 最终输出视频
└── data/               # SQLite 数据库（gitignored，运行时自动创建）
```

---

## 快速开始

### 1. 配置 API 密钥

复制模板并填入真实密钥：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
DEEPSEEK_API_KEY=your_key_here   # https://platform.deepseek.com/api_keys
QWEN_API_KEY=your_key_here       # https://dashscope.aliyuncs.com/
MODELSCOPE_API_KEY=your_key_here # https://modelscope.cn（可选）
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

> Whisper 首次运行会自动下载模型（约 140MB），需要网络。

### 3. 安装 Remotion 依赖

```bash
cd remotion
npm install
```

> 需要 Node.js 18+。如未安装：https://nodejs.org

### 4. 放入 BGM（可选）

将免版权 `.mp3` 文件放入 `assets/bgm/`，有配音时 BGM 自动降为背景音量（10%）。

### 5. 启动

双击 `start.bat`，或：

```bash
python main.py
```

浏览器打开 **http://localhost:7860**

---

## 使用说明

### Mode A — AI 全自动生成

1. 在「岗位描述」框输入招工信息
   ```
   示例：蒙古国招木工，月入15000，包吃住，59岁以下均可，3月出发
   ```
2. 点击「🚀 生成视频」，三步自动完成：
   - **脚本**：DeepSeek 生成视频脚本、场景列表、标题
   - **配图**：Qwen Image Turbo 并行生成 8 张场景配图
   - **配音 + 渲染**：edge-tts 生成普通话配音，Remotion 合成最终视频（约 2-5 分钟）
3. 预览视频满意后，勾选平台，点击「📤 上传到平台」

### Mode B — 素材优化

1. 上传原始视频素材（公司实拍footage等）
2. 可选填写补充岗位说明
3. 点击「🔍 分析素材」，等待 Whisper 转写 + Qwen-VL 场景识别
4. 确认分析结果后，点击「✨ 生成重制版」
5. 预览后上传

### 历史记录

点击「🔄 刷新」查看所有生成记录（最近50条），支持导出 CSV。

---

## 视频规格

| 参数 | 值 |
|------|----|
| 分辨率 | 1080 × 1920（竖屏 9:16） |
| 帧率 | 30 fps |
| 渲染并发 | 4 线程 |
| 帧格式 | JPEG（渲染速度更快） |
| 配音音量 | 100%（主音轨） |
| BGM音量 | 30%（无配音） / 10%（有配音时） |

---

## 素材库使用

```
assets/
├── bgm/    放入 .mp3 文件，视频合成时自动使用第一个文件
└── fonts/  放入 .ttf 字体文件（Remotion 渲染时可引用）
```

---

## 平台上传说明

上传功能目前为**占位实现**，调用后会打印日志但不实际上传。

真实上传实现方案见 `scripts/` 目录下各平台的说明文件，基于 Playwright 自动化。实现前需要：

1. 各平台账号已登录，保存 cookie 至 `cookies/` 目录
2. 安装 Playwright：`pip install playwright && playwright install chromium`
3. 按 Skill 定义文件实现对应 Python 上传脚本

**各平台注意事项：**

- **快手**：发布间隔建议 ≥ 30 分钟，每天每账号 ≤ 3 条
- **抖音**：DOM 结构变更频繁，选择器需定期维护
- **视频号**：首次必须微信扫码登录，Cookie 有效期约 7 天

---

## 内容合规

- 不得承诺虚假工资，工资范围必须来自真实单子
- 不得使用他人真实照片（AI生成图片需注意人脸）
- 海外项目标注「具体以合同为准」
- 各平台不能直接写微信号，使用谐音/图片/评论引导

---

## 依赖说明

| 库 | 用途 |
|----|------|
| gradio | Web UI 界面 |
| openai | DeepSeek API（兼容接口），含自动重试 |
| dashscope | Qwen Image Turbo 图片生成 + Qwen-VL 帧分析 |
| edge-tts | 微软 Azure 中文 TTS 配音（免费，云希/晓晓等声音） |
| openai-whisper | 本地语音转文字（Mode B） |
| ffmpeg-python | 视频抽帧 + 音频提取 |
| Pillow | 图片处理 |
| requests | 图片生成轮询 |
| remotion（npm） | React 视频渲染引擎，SwiftShader 软件渲染 |

---

## 常见问题

**Q：生成卡在「正在合成视频」很久？**
Remotion 渲染 ~1000 帧需要 2-5 分钟，超时上限为 15 分钟。请耐心等待，不要关闭窗口。

**Q：配音没有声音？**
检查 edge-tts 是否正确安装（`pip install edge-tts`），需要网络连接微软服务。

**Q：视频无背景音乐？**
在 `assets/bgm/` 目录放入 `.mp3` 文件后重新生成。

**Q：字幕出现乱码或显示异常？**
确认系统已安装中文字体（Windows 默认已有），Remotion 使用 SwiftShader 软件渲染规避 GPU 驱动问题。
