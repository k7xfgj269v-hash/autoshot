import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # 自动加载项目根目录的 .env 文件

# ── API 配置（通过环境变量或 .env 文件配置，参见 .env.example）──
# DeepSeek: https://platform.deepseek.com/api_keys
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# DashScope (Qwen图片生成 + Qwen-VL视觉理解): https://dashscope.aliyuncs.com/
QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "")
QWEN_IMAGE_MODEL = os.environ.get("QWEN_IMAGE_MODEL", "wanx2.0-t2i-turbo")

# ModelScope (图片生成备选): https://modelscope.cn → 访问令牌
MODELSCOPE_API_KEY = os.environ.get("MODELSCOPE_API_KEY", "")

#── 路径配置 ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
UPLOADS_DIR = BASE_DIR / "uploads"
ASSETS_DIR = BASE_DIR / "assets"
BGM_DIR = ASSETS_DIR / "bgm"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "jobs.db"
REMOTION_DIR = BASE_DIR / "remotion"

# ── 视频规格 ──────────────────────────────────────────────
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_BITRATE = "3000k"

# ── 并发配置 ──────────────────────────────────────────────
IMAGE_GEN_CONCURRENCY = 2  # 图片并行生成数，受 API 并发限制

# ── openclaw 通知 ─────────────────────────────────────────
OPENCLAW_CMD        = "openclaw"                  # 可执行路径，空字符串则禁用通知
OPENCLAW_SESSION_ID = "main"                      # --session-id（通常为 "main"）
OPENCLAW_PLATFORMS  = "kuaishou,douyin,shipinhao"

# ── DeepSeek Prompt 模板 ──────────────────────────────────
SCRIPT_PROMPT_MODE_A = """你是一个招工短视频文案专家，专注下沉市场，语言简单直接。

请根据岗位信息生成：
1. 视频标题（20字以内，含金额，有冲击力）
2. 口播文案（60-90秒，开头5秒必须说出最高工资）
3. 字幕文本列表（和口播一致，分句断行）
4. 话题标签列表（10个：务工/招工/月入XX/目标城市）
5. 封面文案（10字以内）
6. 场景列表（每个场景含 text/duration_sec/image_prompt）
7. 背景音乐风格（bgm_style）

要求：开头直接说钱，语气像老乡介绍，结尾固定：有意向的加我微信，免费了解详情。

严格输出 JSON 格式：
{
  "title": "...",
  "script": "...",
  "subtitles": ["..."],
  "tags": ["..."],
  "cover_text": "...",
  "scenes": [{"text": "...", "duration_sec": 3, "image_prompt": "..."}],
  "bgm_style": "..."
}"""

SCRIPT_PROMPT_MODE_B = """你是一个招工短视频文案专家。根据岗位信息、原视频转写文本和场景描述，生成优化后的视频脚本。

输出与 Mode A 相同的 JSON 格式，但 scenes 中每项额外包含 source_timestamp_sec 字段（对应原视频时间点）。

严格输出 JSON 格式：
{
  "title": "...",
  "script": "...",
  "subtitles": ["..."],
  "tags": ["..."],
  "cover_text": "...",
  "scenes": [{"text": "...", "duration_sec": 3, "image_prompt": "...", "source_timestamp_sec": 0}],
  "bgm_style": "..."
}"""
