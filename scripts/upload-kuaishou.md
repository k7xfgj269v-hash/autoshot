---
name: upload-kuaishou
version: 1.0.0
description: 自动上传招工视频到快手创作者平台
trigger: 当 upload_to_platforms() 的 platforms 包含 'kuaishou' 时调用
---

# Upload to 快手

## Trigger
当主流程生成视频后，用户选择上传到快手平台时触发。

## Inputs
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| video_path | str | ✅ | 本地视频文件绝对路径 (.mp4) |
| title | str | ✅ | 视频标题（≤20字） |
| description | str | ❌ | 视频描述文本 |
| tags | list[str] | ❌ | 话题标签列表（不含#号） |
| cover_path | str | ❌ | 封面图片路径 |

## Steps（Playwright 伪代码）

```python
# Step 1: 打开快手创作者中心
browser.goto("https://cp.kuaishou.com/article/publish/video")

# Step 2: 等待登录状态（需预先保存 cookie）
# 若未登录，加载 cookies/kuaishou.json 并刷新页面
if not is_logged_in():
    context.add_cookies(load_cookies("kuaishou"))
    browser.reload()

# Step 3: 上传视频文件
upload_btn = page.locator("input[type='file']")
upload_btn.set_input_files(video_path)
page.wait_for_selector(".upload-progress-done", timeout=120000)

# Step 4: 填写标题
title_input = page.locator(".title-input")
title_input.fill(title)

# Step 5: 添加话题标签
for tag in tags[:5]:
    page.click(".add-topic-btn")
    page.fill(".topic-search-input", tag)
    page.click(".topic-result-item:first-child")

# Step 6: 上传封面（可选）
if cover_path:
    cover_btn = page.locator(".cover-upload-btn")
    cover_btn.click()
    page.locator("input.cover-file-input").set_input_files(cover_path)

# Step 7: 点击发布
page.click(".publish-btn")
page.wait_for_selector(".publish-success", timeout=30000)

# Step 8: 获取发布 URL
post_url = page.url
```

## Output
```json
{
  "platform": "kuaishou",
  "status": "success" | "failed",
  "post_url": "https://www.kuaishou.com/short-video/...",
  "error": null | "错误描述"
}
```

## Error Handling & Retry
- 上传超时（>120s）：重试 2 次，指数退避
- 登录失效：停止执行，提示用户重新登录并保存 cookie
- 发布按钮未找到：截图保存，记录错误，跳过本次上传

## Notes
⚠️ **此文件为技能定义，不包含真实 Playwright 实现代码**
- 快手平台有反爬机制，建议：上传间隔 ≥ 30 分钟
- Cookie 文件保存在 `cookies/kuaishou.json`，需定期更新
- 标题不能包含电话号码或微信号（平台会屏蔽）
- 建议人工确认发布结果后再关闭浏览器
