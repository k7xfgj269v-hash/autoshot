import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Generator, Optional
import threading
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
import requests
import ffmpeg
import dashscope
from dashscope import MultiModalConversation
from src.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    QWEN_API_KEY, QWEN_IMAGE_MODEL, MODELSCOPE_API_KEY,
    BASE_DIR, OUTPUT_DIR, SCRIPT_PROMPT_MODE_A,
    DB_PATH, DATA_DIR, UPLOADS_DIR,
    BGM_DIR, REMOTION_DIR, SCRIPT_PROMPT_MODE_B,
    IMAGE_GEN_CONCURRENCY, OPENCLAW_CMD, OPENCLAW_SESSION_ID, OPENCLAW_PLATFORMS,
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局模型缓存
_WHISPER_MODEL = None
_WHISPER_LOCK = threading.Lock()

def get_whisper_model():
    """获取或加载 Whisper 模型单例（线程安全）"""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        with _WHISPER_LOCK:
            if _WHISPER_MODEL is None:  # 双重检查，防止并发重复加载
                try:
                    import whisper
                    logger.info("[Whisper] 正在加载模型实例 (base)...")
                    _WHISPER_MODEL = whisper.load_model("base")
                except Exception as e:
                    logger.error(f"加载 Whisper 模型失败: {e}")
                    raise
    return _WHISPER_MODEL

def validate_config():
    """启动前校验配置有效性"""
    missing = []
    if not DEEPSEEK_API_KEY or "YOUR_" in DEEPSEEK_API_KEY or len(DEEPSEEK_API_KEY) < 20: missing.append("DeepSeek API Key")
    if not QWEN_API_KEY or "YOUR_" in QWEN_API_KEY or len(QWEN_API_KEY) < 20: missing.append("Qwen API Key")
    if not MODELSCOPE_API_KEY or "YOUR_" in MODELSCOPE_API_KEY or len(MODELSCOPE_API_KEY) < 20: missing.append("ModelScope API Key")
    for d in [OUTPUT_DIR, DATA_DIR, UPLOADS_DIR]:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            missing.append(f"目录创建失败 ({d.name}): {e}")
    if missing:
        logger.warning(f"配置预检未完全通过: {', '.join(missing)}")
    else:
        logger.info("✅ 核心配置校验通过")

_OPENAI_CLIENT: OpenAI | None = None
_OPENAI_CLIENT_LOCK = threading.Lock()

def get_openai_client() -> OpenAI:
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        with _OPENAI_CLIENT_LOCK:
            if _OPENAI_CLIENT is None:
                _OPENAI_CLIENT = OpenAI(
                    api_key=DEEPSEEK_API_KEY,
                    base_url=DEEPSEEK_BASE_URL,
                    max_retries=0,   # _call_deepseek 自己处理重试，避免 SDK 重试叠加
                    timeout=120.0,
                )
    return _OPENAI_CLIENT

def _call_deepseek(messages: list, max_attempts: int = 3) -> str:
    """调用 DeepSeek，对 RemoteProtocolError / APIConnectionError 做手动重试"""
    client = get_openai_client()
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
            )
            if not response.choices:
                raise RuntimeError("DeepSeek API 返回空 choices 列表")
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("DeepSeek API 返回空 content")
            return content
        except RuntimeError:
            raise  # 逻辑错误（空 choices/content），无需重试
        except Exception as e:
            last_exc = e
            logger.warning(f"DeepSeek 调用失败 (第{attempt}次): {e}")
            if attempt < max_attempts:
                time.sleep(3 * attempt)
    raise last_exc

def generate_script(job_text: str, progress=None) -> dict:
    """调用 DeepSeek API 生成脚本"""
    if progress: progress(0.1, desc="🚀 正在构思创意脚本...")
    try:
        content = _call_deepseek([
            {"role": "system", "content": SCRIPT_PROMPT_MODE_A},
            {"role": "user", "content": f"岗位信息：{job_text}"},
        ])
        return json.loads(content)
    except Exception as e:
        logger.error(f"DeepSeek API 失败: {e}")
        raise RuntimeError(f"脚本生成失败: {e}")

def _generate_single_image(prompt: str, img_path: Path) -> str:
    """单张图片生成的内部实现，带主备切换"""
    # 主力：DashScope（网络/超时异常最多重试1次，审核拒绝直接降级）
    for attempt in range(2):
        task_hard_failed = False
        try:
            sub = requests.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                headers={"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json", "X-DashScope-Async": "enable"},
                json={"model": QWEN_IMAGE_MODEL, "input": {"prompt": prompt}, "parameters": {"size": "720*1280", "n": 1}},
                timeout=30
            )
            sub.raise_for_status()
            task_id = sub.json()["output"]["task_id"]
            deadline = time.time() + 180
            poll_count = 0
            while time.time() < deadline:
                time.sleep(min(2 ** poll_count, 10))
                poll_count += 1
                poll = requests.get(f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                                    headers={"Authorization": f"Bearer {QWEN_API_KEY}"}, timeout=15)
                pd_data = poll.json()
                task_status = pd_data.get("output", {}).get("task_status")
                if task_status == "SUCCEEDED":
                    results_list = pd_data.get("output", {}).get("results", [])
                    if not results_list:
                        logging.warning("DashScope SUCCEEDED but results list is empty")
                        task_hard_failed = True
                        break
                    img_url = results_list[0]["url"]
                    img_data = requests.get(img_url, timeout=30).content
                    img_path.write_bytes(img_data)
                    return str(img_path)
                elif task_status == "FAILED":
                    logging.warning(f"DashScope task FAILED (可能触发内容审核): {pd_data.get('output', {})}")
                    task_hard_failed = True  # 审核拒绝，重试无意义
                    break
                # task_status == "RUNNING" 继续轮询
        except Exception as e:
            logging.warning(f"DashScope attempt {attempt} 异常: {e}")
            time.sleep(1)
        if task_hard_failed:
            break  # 跳出 for，直接降级 ModelScope

    # ModelScope Fallback
    try:
        resp = requests.post(
            "https://api-inference.modelscope.cn/v1/images/generations",
            headers={"Authorization": f"Bearer {MODELSCOPE_API_KEY}", "Content-Type": "application/json", "X-ModelScope-Async-Mode": "true"},
            json={"model": "Tongyi-MAI/Z-Image-Turbo", "prompt": prompt, "width": 576, "height": 1024},
            timeout=60
        )
        resp.raise_for_status()
        res = resp.json()
        task_id = res.get("task_id")
        if task_id:
            deadline = time.time() + 180
            poll_count = 0
            while time.time() < deadline:
                time.sleep(min(2 ** poll_count, 10))
                poll_count += 1
                poll = requests.get(f"https://api-inference.modelscope.cn/v1/tasks/{task_id}",
                                    headers={"Authorization": f"Bearer {MODELSCOPE_API_KEY}"}, timeout=15)
                data = poll.json()
                if data.get("task_status") == "SUCCEED":
                    output_images = data.get("output_images", [])
                    if not output_images:
                        raise RuntimeError("ModelScope SUCCEED but output_images is empty")
                    img_url = output_images[0]
                    img_path.write_bytes(requests.get(img_url, timeout=30).content)
                    return str(img_path)
            raise RuntimeError("ModelScope 任务超时（>180s）")
        raise RuntimeError("ModelScope 未返回 task_id")
    except RuntimeError:
        raise  # 逻辑错误直接上抛，不再包裹
    except Exception as e:
        raise RuntimeError(f"所有方案均失败: {e}")

def generate_images(script_json: dict, progress=None) -> Generator[list[str], None, None]:
    """并行配图，每张图完成时实时 yield 进度"""
    scenes = script_json.get("scenes", [])
    if not scenes:
        raise RuntimeError("脚本中没有 scenes，无法生成配图")
    prompts = [s.get("image_prompt", "专业工作场景") for s in scenes]
    img_dir = OUTPUT_DIR / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    job_id = str(uuid.uuid4())[:8]
    paths: list[str | None] = [None] * len(scenes)
    total = len(prompts)

    q: Queue = Queue()

    def _worker(idx: int, prompt: str, path: Path):
        try:
            result = _generate_single_image(prompt, path)
            q.put((idx, result, None))
        except Exception as e:
            q.put((idx, "", e))

    with ThreadPoolExecutor(max_workers=IMAGE_GEN_CONCURRENCY) as executor:
        for i, p in enumerate(prompts):
            executor.submit(_worker, i, p, img_dir / f"{job_id}_{i:02d}.png")

        for completed in range(1, total + 1):
            idx, result, err = q.get()
            if err:
                logger.error(f"Image {idx} failed: {err}")
                paths[idx] = ""
            else:
                paths[idx] = result
            if progress:
                progress(0.2 + (completed / total) * 0.5, desc=f"🎨 正在绘图 ({completed}/{total})...")
            yield [p for p in paths if p]

    failed = [i for i, p in enumerate(paths) if not p]
    if len(failed) == total:
        raise RuntimeError(f"所有图片生成失败，槽位: {failed}")
    elif failed:
        logging.warning(f"以下图片槽位生成失败: {failed}")

def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, mode TEXT, job_text TEXT, video_path TEXT, duration_sec REAL, status TEXT, platform_log TEXT)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_at ON jobs(created_at)")
        conn.commit()

def save_record(mode, job_text, video_path, duration_sec, status, platform_log="") -> int:
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        cursor = conn.execute("INSERT INTO jobs (created_at, mode, job_text, video_path, duration_sec, status, platform_log) VALUES (?,?,?,?,?,?,?)",
                             (datetime.now(timezone.utc).isoformat(), mode, job_text, video_path, duration_sec, status, platform_log))
        rowid = cursor.lastrowid
        conn.commit()
    return rowid

def upload_to_platforms(video_path, platforms) -> str:
    # TODO: 接入各平台开放平台 API（快手/抖音/视频号均需申请开发者权限并配置 access_token）
    # 当前为占位实现，不执行真实上传
    raise NotImplementedError(
        "upload_to_platforms 尚未实现。"
        "需要分别接入：快手开放平台 /upload API、抖音开放平台 /video/upload、微信视频号上传接口。"
        "请在 config.py 中添加各平台 access_token 后实现本函数。"
    )

def extract_media(video_path):
    try:
        vid_id = str(uuid.uuid4())[:8]
        d = OUTPUT_DIR / "frames" / vid_id
        d.mkdir(parents=True, exist_ok=True)
        probe = ffmpeg.probe(video_path)
        dur = float(probe["format"]["duration"])
        has_audio = any(s.get("codec_type") == "audio" for s in probe.get("streams", []))
        inp = ffmpeg.input(video_path)
        video_out = inp.output(str(d / "f_%d.jpg"), vf="fps=1")
        if has_audio:
            ap = d / "a.wav"
            audio_out = inp.output(str(ap), acodec="pcm_s16le", ac=1, ar="16000")
            ffmpeg.merge_outputs(video_out, audio_out).run(quiet=True, overwrite_output=True)
            audio_path = str(ap)
        else:
            logger.warning(f"视频无音频流，跳过音频提取: {video_path}")
            video_out.run(quiet=True, overwrite_output=True)
            audio_path = ""
        frame_paths = sorted(d.glob("f_*.jpg"), key=lambda p: int(p.stem.split("_")[1]))
        frame_paths = [str(p) for p in frame_paths]
        return {"frame_paths": frame_paths, "audio_path": audio_path, "duration_sec": dur}
    except Exception as e:
        raise RuntimeError(f"extract_media 失败 ({video_path}): {e}") from e

def transcribe_audio(audio_path):
    try:
        return get_whisper_model().transcribe(audio_path, language="zh")["text"]
    except Exception as e:
        raise RuntimeError(f"transcribe_audio 失败 ({audio_path}): {e}") from e

def analyze_frames(frame_paths):
    try:
        content = [{"image": str(p)} for p in frame_paths[:5]] + [{"text": "描述画面内容"}]
        res = MultiModalConversation.call(model="qwen-vl-plus", messages=[{"role": "user", "content": content}])
        if res is None or res.output is None:
            raise RuntimeError("DashScope 返回空响应")
        choices = res.output.choices
        if not choices:
            raise RuntimeError("DashScope 返回空 choices 列表")
        content = choices[0].message.content
        if not content:
            raise RuntimeError("DashScope 返回空 content 列表")
        return content[0]["text"]
    except Exception as e:
        raise RuntimeError(f"analyze_frames 失败: {e}") from e

def generate_tts(text: str, output_path: Path, voice: str = "zh-CN-YunxiNeural") -> Optional[str]:
    """使用 edge-tts 生成中文配音，失败时返回 None（不阻塞渲染）。
    在独立线程中运行自己的事件循环，避免与 Gradio 的事件循环冲突。
    """
    try:
        import edge_tts

        async def _save():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))

        exc_box: list[BaseException] = []

        def _run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_save())
            except Exception as e:
                exc_box.append(e)
            finally:
                loop.close()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        t = threading.Thread(target=_run_in_thread, daemon=True)
        t.start()
        t.join(timeout=60)
        if t.is_alive():
            raise RuntimeError("TTS 超时（>60s）")
        if exc_box:
            raise exc_box[0]
        logger.info(f"TTS 配音生成成功: {output_path.name}")
        return str(output_path)
    except Exception as e:
        logger.warning(f"TTS 配音生成失败，将无配音: {e}")
        return None


def _run_remotion(cmd: list, cwd: str, max_retries: int = 2) -> None:
    """运行 Remotion CLI，失败自动重试。
    在 Windows 上用 list2cmdline 将参数列表转为正确引号的字符串再传给 shell，
    避免路径中含空格时参数被截断。
    """
    cmd_str = subprocess.list2cmdline(cmd)
    last_err = None
    for attempt in range(max_retries):
        try:
            subprocess.run(cmd_str, cwd=cwd, check=True, capture_output=True, timeout=900, shell=True)
            return
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("Remotion 渲染超时（>900s），请检查 Node.js 环境或减少场景数量") from e
        except subprocess.CalledProcessError as e:
            last_err = e
            if attempt < max_retries - 1:
                logger.warning(f"Remotion 渲染失败（第 {attempt + 1} 次），3 秒后重试...")
                time.sleep(3)
    raise RuntimeError(f"Remotion 渲染失败:\n{last_err.stderr.decode(errors='replace')}") from last_err


def _to_posix(p: Path | str, base: Path) -> str:
    """将路径转为相对于 base 的 POSIX 字符串；不在 base 下时回退为绝对 POSIX 路径。"""
    try:
        return Path(p).relative_to(base).as_posix()
    except ValueError:
        return Path(p).as_posix()


def _get_audio_duration(audio_path: str) -> float:
    """用 ffprobe 获取音频实际时长（秒）"""
    probe = ffmpeg.probe(audio_path)
    return float(probe["format"]["duration"])


def _generate_tts_per_scene(scenes: list, job_id: str, voice: str = "zh-CN-YunxiNeural") -> tuple:
    """为每个场景单独生成 TTS 片段，拼接成完整音频。
    返回 (concat_mp3_path_or_None, updated_scenes_with_exact_durations)
    """
    tts_dir = OUTPUT_DIR / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    clip_paths = []
    updated_scenes = []
    for i, scene in enumerate(scenes):
        text = scene.get("text", "").strip()
        if not text:
            updated_scenes.append(scene)
            clip_paths.append(None)
            continue
        clip_path = tts_dir / f"{job_id}_scene_{i:02d}.mp3"
        result = generate_tts(text, clip_path, voice)
        if result:
            try:
                dur = _get_audio_duration(result)
                updated_scenes.append({**scene, "duration_sec": round(dur, 3)})
                clip_paths.append(result)
            except Exception:
                updated_scenes.append(scene)
                clip_paths.append(result)
        else:
            updated_scenes.append(scene)
            clip_paths.append(None)

    valid = [p for p in clip_paths if p]
    if not valid:
        return None, updated_scenes

    concat_path = tts_dir / f"{job_id}_full.mp3"
    list_file = tts_dir / f"{job_id}_concat.txt"
    list_file.write_text("\n".join(f"file '{Path(p).as_posix()}'" for p in valid), encoding="utf-8")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(concat_path)],
            check=True, capture_output=True,
        )
        list_file.unlink(missing_ok=True)
        logger.info(f"[tts-sync] 逐场景 TTS 拼接完成: {concat_path.name}")
        return str(concat_path), updated_scenes
    except Exception as e:
        logger.warning(f"[tts-sync] 拼接失败，回退整段 TTS: {e}")
        list_file.unlink(missing_ok=True)
        return None, updated_scenes


def notify_openclaw(video_path: str, title: str, tags: list) -> None:
    """视频生成完成后非阻塞通知 openclaw agent 触发上传（fire-and-forget）"""
    if not OPENCLAW_CMD:
        return
    msg = (
        f"新视频已生成，请上传到 {OPENCLAW_PLATFORMS}。"
        f" 标题：{title}"
        f" 路径：{video_path}"
        f" 标签：{', '.join(str(t) for t in tags)}"
    )
    cmd = [
        OPENCLAW_CMD, "agent",
        "--local",
        "--session-id", OPENCLAW_SESSION_ID,
        "--message", msg,
    ]
    subprocess.Popen(subprocess.list2cmdline(cmd), shell=True)
    logger.info(f"[openclaw] 已通知上传: {video_path}")


def render_video_mode_a(script_json, image_paths, progress=None) -> dict:
    if progress: progress(0.8, desc="🎬 正在通过 Remotion 合成视频...")
    v_dir = OUTPUT_DIR / "videos"
    v_dir.mkdir(parents=True, exist_ok=True)
    out = v_dir / f"{str(uuid.uuid4())[:8]}_mode_a.mp4"
    bgm_all = sorted(BGM_DIR.glob("*.mp3"))
    if not bgm_all:
        logging.warning(f"BGM_DIR ({BGM_DIR}) 中未找到 .mp3 文件，将以无 BGM 渲染")
        bgm = []
    else:
        bgm_style = script_json.get("bgm_style", "")
        # 用 bgm_style 关键词模糊匹配文件名，无匹配则取第一个
        matched = [f for f in bgm_all if any(kw in f.stem for kw in bgm_style.split())] if bgm_style else []
        bgm = matched if matched else bgm_all
    job_id = str(uuid.uuid4())[:8]
    tts_path, scenes = _generate_tts_per_scene(script_json["scenes"], job_id)
    if not tts_path:
        # 逐场景失败时回退整段 TTS
        tts_text = script_json.get("script", "") or " ".join(s.get("text", "") for s in scenes)
        tts_path = generate_tts(tts_text, OUTPUT_DIR / "tts" / f"{job_id}_voice.mp3")
        scenes = script_json["scenes"]

    props = {
        "scenes": scenes,
        "imagePaths": [_to_posix(p, BASE_DIR) for p in image_paths],
        "bgmPath": _to_posix(bgm[0], BASE_DIR) if bgm else None,
        "voicePath": _to_posix(tts_path, BASE_DIR) if tts_path else None,
        "title": script_json.get("title", ""),
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(props, f)
        pf = f.name
    try:
        _run_remotion(
            ["npx", "remotion", "render", "src/index.tsx", "ModeA", Path(out).as_posix(),
             f"--props={Path(pf).as_posix()}", f"--public-dir={BASE_DIR.as_posix()}",
             "--concurrency=4", "--image-format=jpeg", "--gl=swiftshader"],
            cwd=str(REMOTION_DIR),
        )
        # duration_sec 为脚本估算值，非实际渲染时长
        return {"video_path": str(out), "duration_sec": sum(s.get("duration_sec", 3) for s in scenes), "mode": "A"}
    finally:
        if os.path.exists(pf): os.unlink(pf)

def generate_script_mode_b(job_text, transcript, scene_desc, progress=None) -> dict:
    if progress: progress(0.5, desc="🧠 正在优化脚本...")
    try:
        content = _call_deepseek([
            {"role": "system", "content": SCRIPT_PROMPT_MODE_B},
            {"role": "user", "content": f"岗位：{job_text}\n素材：{transcript}\n画面：{scene_desc}"},
        ])
        return json.loads(content)
    except Exception as e:
        raise RuntimeError(f"Mode B 脚本生成失败: {e}") from e

def render_video_mode_b(script_json, source_video, progress=None) -> dict:
    if progress: progress(0.8, desc="🎬 正在应用优化...")
    v_dir = OUTPUT_DIR / "videos"
    v_dir.mkdir(parents=True, exist_ok=True)
    out = v_dir / f"{str(uuid.uuid4())[:8]}_mode_b.mp4"
    # 将用户上传的视频复制到 UPLOADS_DIR，确保在 public-dir 范围内
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    vid_dest = UPLOADS_DIR / f"{uuid.uuid4().hex[:8]}_{Path(source_video).name}"
    shutil.copy2(source_video, vid_dest)
    props = {
        "scenes": script_json["scenes"],
        "sourceVideo": _to_posix(vid_dest, BASE_DIR),
        "title": script_json.get("title", ""),
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(props, f)
        pf = f.name
    try:
        _run_remotion(
            ["npx", "remotion", "render", "src/index.tsx", "ModeB", Path(out).as_posix(),
             f"--props={Path(pf).as_posix()}", f"--public-dir={BASE_DIR.as_posix()}",
             "--concurrency=4", "--image-format=jpeg", "--gl=swiftshader"],
            cwd=str(REMOTION_DIR),
        )
        # duration_sec 为脚本估算值，非实际渲染时长
        return {"video_path": str(out), "duration_sec": sum(s.get("duration_sec", 3) for s in script_json["scenes"]), "mode": "B"}
    finally:
        if os.path.exists(pf): os.unlink(pf)
        try:
            vid_dest.unlink(missing_ok=True)
        except Exception:
            pass

_initialized = False
_startup_lock = threading.Lock()

def _startup():
    global _initialized
    if not _initialized:
        with _startup_lock:
            if not _initialized:
                validate_config()
                init_db()
                dashscope.api_key = QWEN_API_KEY
                _initialized = True

_startup()
