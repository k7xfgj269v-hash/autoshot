import logging
import os
import sqlite3
import socket
import csv
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import gradio as gr

logger = logging.getLogger(__name__)
from src.pipeline import (
    generate_script,
    generate_images,
    render_video_mode_a,
    extract_media,
    transcribe_audio,
    analyze_frames,
    generate_script_mode_b,
    render_video_mode_b,
    save_record,
    upload_to_platforms,
    notify_openclaw,
)
from src.config import DB_PATH, OUTPUT_DIR

os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

MAX_JOB_TEXT_LEN = 2000
ALLOWED_VIDEO_TYPES = {".mp4", ".mov", ".avi", ".mkv"}

# ── 自定义 CSS ───────────────────────────────────────────
CUSTOM_CSS = """
body { background-color: #f0f2f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
.header-box { text-align: center; padding: 2rem 0; background: linear-gradient(135deg, #2c3e50, #4ca1af); color: white; border-radius: 12px; margin-bottom: 2rem; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
.card-group { border-radius: 12px !important; border: 1px solid #e0e0e0 !important; background: white !important; box-shadow: 0 2px 10px rgba(0,0,0,0.05) !important; padding: 1.5rem !important; }
.primary-btn { background: linear-gradient(135deg, #4ca1af, #2c3e50) !important; color: white !important; font-weight: bold !important; border: none !important; }
.secondary-btn { border: 2px solid #4ca1af !important; color: #4ca1af !important; background: transparent !important; }
.status-msg { border-left: 5px solid #4ca1af; background: #f8f9fa; font-weight: 500; }
footer { display: none !important; }
"""

# ── 工具函数 ──────────────────────────────────────────────

def _get_file_path(f) -> str:
    if isinstance(f, (str, Path)):
        return str(f)
    if hasattr(f, "name"):  # file-like objects (NamedTemporaryFile 等)
        return f.name
    if isinstance(f, dict):
        return f.get("name") or f.get("path") or str(f)
    return str(f)


def find_free_port():
    for p in range(7860, 7880):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", p))
                return p
        except OSError:
            continue
    return 7860


def _upload_wrapper(video_path, platforms):
    try:
        result = upload_to_platforms(video_path, platforms)
        if isinstance(result, dict):
            return "\n".join(f"{p}: ✅ 已发布" for p in result)
        return result
    except NotImplementedError as e:
        return f"⚠️ {e}"
    except Exception as e:
        traceback.print_exc()
        return f"❌ 发布失败：{e}"


# ── 核心处理函数 ──────────────────────────────────────────────

def process_mode_a(job_text: str, progress=gr.Progress()):
    """Mode A 的业务逻辑封装，支持进度条"""
    if not job_text.strip():
        yield "❌ 请输入岗位描述", None, None, None
        return
    if len(job_text) > MAX_JOB_TEXT_LEN:
        yield f"❌ 岗位描述过长（{len(job_text)} 字），请控制在 {MAX_JOB_TEXT_LEN} 字以内", None, None, None
        return

    try:
        # Step 1: Script
        script_json = generate_script(job_text, progress=progress)

        # Step 2: Images
        image_paths = []
        for current_images in generate_images(script_json, progress=progress):
            image_paths = current_images
            yield f"⏳ 正在生成配图 ({len(image_paths)}/8)...", script_json, image_paths, None

        # Step 3: Render
        yield "⏳ 图片生成完毕，正在合成视频（约1-3分钟）...", script_json, image_paths, None
        result = render_video_mode_a(script_json, image_paths, progress=progress)
        save_record("A", job_text, result["video_path"], result["duration_sec"], "done")
        try:
            notify_openclaw(result["video_path"], script_json.get("title", ""), script_json.get("tags", []))
        except Exception as e:
            logger.warning(f"openclaw 通知失败（不影响生成结果）: {e}")

        yield f"✅ 生成成功！时长：{result['duration_sec']:.1f}s", script_json, image_paths, result["video_path"]
    except Exception as e:
        traceback.print_exc()
        yield f"❌ 错误：{str(e)}", None, None, None


def process_analyze_b(video_file, job_text, progress=gr.Progress()):
    """Mode B 第一步：分析素材"""
    if video_file is None:
        return "❌ 请上传视频", "", ""

    try:
        video_path = _get_file_path(video_file)
        if not any(video_path.lower().endswith(ext) for ext in ALLOWED_VIDEO_TYPES):
            return f"❌ 不支持的文件格式，请上传 {'/'.join(ALLOWED_VIDEO_TYPES)} 文件", "", ""
        progress(0.2, desc="🔍 正在提取关键帧与音频...")
        media = extract_media(video_path)

        progress(0.5, desc="🎙️ 转写 & 场景分析并行中...")
        with ThreadPoolExecutor(max_workers=2) as ex:
            ft = ex.submit(transcribe_audio, media["audio_path"]) if media["audio_path"] else None
            fa = ex.submit(analyze_frames, media["frame_paths"])
            transcript = ft.result() if ft else ""
            scene_desc = fa.result()
        progress(0.8, desc="✅ 分析完成")

        return "✅ 分析完成", transcript, scene_desc
    except Exception as e:
        traceback.print_exc()
        return f"❌ 分析失败：{str(e)}", "", ""


def process_mode_b(job_text, transcript, scene_desc, video_file, progress=gr.Progress()):
    """Mode B 第二步：重制生成"""
    if transcript is None or not video_file:
        return "❌ 请先完成素材分析", None
    if job_text and len(job_text) > MAX_JOB_TEXT_LEN:
        return f"❌ 补充说明过长（{len(job_text)} 字），请控制在 {MAX_JOB_TEXT_LEN} 字以内", None

    try:
        video_path = _get_file_path(video_file)
        script_json = generate_script_mode_b(job_text or "", transcript, scene_desc, progress=progress)
        result = render_video_mode_b(script_json, video_path, progress=progress)
        save_record("B", job_text, result["video_path"], result["duration_sec"], "done")
        try:
            notify_openclaw(result["video_path"], script_json.get("title", ""), script_json.get("tags", []))
        except Exception as e:
            logger.warning(f"openclaw 通知失败（不影响生成结果）: {e}")
        return f"✅ 优化视频生成成功！", result["video_path"]
    except Exception as e:
        traceback.print_exc()
        return f"❌ 错误：{str(e)}", None


def load_history():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT id, created_at, mode, job_text, video_path, duration_sec, status, platform_log FROM jobs ORDER BY id DESC LIMIT 50")
            rows = cursor.fetchall()
        return [list(row) for row in rows]
    except Exception as e:
        print(f"[load_history] DB error: {e}")
        return []


def export_history_to_csv():
    try:
        rows = load_history()
        csv_path = OUTPUT_DIR / "jobs_history.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "时间", "模式", "内容", "路径", "时长", "状态", "日志"])
            writer.writerows(rows)
        return gr.update(value=str(csv_path), visible=True)
    except Exception as e:
        traceback.print_exc()
        return gr.update(visible=False)


# ── UI 布局 ──────────────────────────────────────────────

with gr.Blocks(title="招工视频助手 v2.0") as demo:
    gr.HTML("<div class='header-box'><h1>🎬 招工视频助手 v2.0</h1><p>由 DeepSeek & Qwen / Remotion 提供技术支持</p></div>")

    with gr.Tabs():
        # Mode A
        with gr.TabItem("Mode A — AI生成"):
            with gr.Row():
                with gr.Column(scale=4):
                    with gr.Group(elem_classes="card-group"):
                        gr.Markdown("### 1. 输入信息")
                        job_input_a = gr.Textbox(label="", placeholder="粘贴岗位描述...", lines=8)
                        btn_example = gr.Button("📋 填入示例")
                        btn_gen_a = gr.Button("🚀 开始生成", variant="primary", elem_classes="primary-btn")
                        status_a = gr.Textbox(label="状态", interactive=False, elem_classes="status-msg")

                with gr.Column(scale=5):
                    with gr.Group(elem_classes="card-group"):
                        gr.Markdown("### 2. 场景配图")
                        gallery_a = gr.Gallery(label="", columns=4, height=300)
                    with gr.Group(elem_classes="card-group"):
                        gr.Markdown("### 脚本JSON")
                        script_json_a = gr.JSON(label="")

            with gr.Row():
                with gr.Column():
                    with gr.Group(elem_classes="card-group"):
                        gr.Markdown("### 3. 成品与发布")
                        video_a = gr.Video(label="")
                        platforms_a = gr.CheckboxGroup(["快手", "抖音", "视频号"], label="平台", value=["快手", "抖音"])
                        btn_up_a = gr.Button("📤 确认发布")
                        up_status_a = gr.Textbox(label="发布日志", interactive=False)

        # Mode B
        with gr.TabItem("Mode B — 素材优化"):
            with gr.Row():
                with gr.Column():
                    with gr.Group(elem_classes="card-group"):
                        gr.Markdown("### 1. 上传素材")
                        file_b = gr.File(label="视频文件", file_types=[".mp4", ".mov", ".avi", ".mkv"])
                        job_input_b = gr.Textbox(label="补充说明")
                        btn_analyze = gr.Button("🔍 智能分析", variant="primary")
                        analyze_status_b = gr.Textbox(label="分析进度", interactive=False)
                with gr.Column():
                    with gr.Group(elem_classes="card-group"):
                        gr.Markdown("### 2. 分析结果")
                        transcript_b = gr.Textbox(label="语音转写", lines=4)
                        scene_desc_b = gr.Textbox(label="场景描述", lines=4)

            with gr.Row():
                with gr.Column():
                    with gr.Group(elem_classes="card-group"):
                        gr.Markdown("### 3. 生成优化视频")
                        btn_gen_b = gr.Button("✨ 生成重制版", variant="primary", elem_classes="primary-btn")
                        status_b = gr.Textbox(label="生成状态", interactive=False)
                        video_b = gr.Video(label="成品预览")

        # History
        with gr.TabItem("历史记录"):
            with gr.Group(elem_classes="card-group"):
                with gr.Row():
                    btn_refresh = gr.Button("🔄 刷新", scale=2)
                    btn_export = gr.Button("📊 导出 CSV", scale=1)
                table_history = gr.Dataframe(headers=["ID", "时间", "模式", "内容", "路径", "时长", "状态", "日志"], interactive=False)
                file_download = gr.File(label="导出文件", visible=False)

    # 事件绑定
    btn_example.click(fn=lambda: "蒙古国招木工，月入15000，包吃住，59岁以下均可，3月出发，待遇优厚。", outputs=job_input_a)
    btn_gen_a.click(fn=process_mode_a, inputs=job_input_a, outputs=[status_a, script_json_a, gallery_a, video_a])

    btn_analyze.click(fn=process_analyze_b, inputs=[file_b, job_input_b], outputs=[analyze_status_b, transcript_b, scene_desc_b])
    btn_gen_b.click(fn=process_mode_b, inputs=[job_input_b, transcript_b, scene_desc_b, file_b], outputs=[status_b, video_b])

    btn_up_a.click(fn=_upload_wrapper, inputs=[video_a, platforms_a], outputs=up_status_a)
    btn_refresh.click(fn=load_history, outputs=table_history)
    btn_export.click(fn=export_history_to_csv, outputs=file_download)
    demo.load(fn=load_history, outputs=table_history)

def run():
    port = find_free_port()
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=port, allowed_paths=[str(OUTPUT_DIR)],
                css=CUSTOM_CSS, theme=gr.themes.Soft(primary_hue="cyan"))

if __name__ == "__main__":
    run()
