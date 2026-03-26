---
name: upload-shipinhao
version: 1.0.0
description: 自动上传短视频到微信视频号创作者平台
trigger: 当 upload_to_platforms() 的 platforms 包含 'shipinhao' 时调用
---

# Upload to 微信视频号

## Trigger
当主流程生成视频后，用户选择上传到视频号时触发。建议在抖音上传后延迟 30 分钟执行。

## Inputs
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| video_path | str | ✅ | 本地视频文件绝对路径 (.mp4) |
| title | str | ✅ | 视频描述/标题（视频号无独立标题字段） |
| tags | list[str] | ❌ | 话题标签 |
| cover_path | str | ❌ | 封面图片路径 |

## Steps（Playwright 伪代码）

```python
# Step 1: 打开视频号助手（需微信扫码登录）
browser.goto("https://channels.weixin.qq.com/platform/post/create")

# Step 2: 处理登录（视频号需微信扫码，无法自动化）
# ⚠️ 首次必须人工扫码，之后 cookie 有效期约 7 天
if not is_logged_in():
    qr_code = page.locator(".qr-code-img")
    print("请用微信扫码登录视频号助手...")
    qr_code.screenshot(path="qr_code.png")
    input("扫码完成后按 Enter 继续...")

# Step 3: 上传视频
page.locator("input[type='file']").set_input_files(video_path)
page.wait_for_selector(".upload-success", timeout=300000)  # 视频号上传较慢

# Step 4: 填写描述
page.fill(".input-desc", title)

# Step 5: 添加话题
for tag in tags[:5]:
    page.click(".add-topic")
    page.fill(".topic-search", f"#{tag}")
    page.keyboard.press("Enter")

# Step 6: 上传封面（可选）
if cover_path:
    page.click(".cover-upload")
    page.locator("input.cover-file").set_input_files(cover_path)
    page.click(".cover-ok-btn")

# Step 7: 发布
page.click(".publish-btn")
page.wait_for_selector(".post-success-toast", timeout=30000)
```

## Output
```json
{
  "platform": "shipinhao",
  "status": "success" | "failed",
  "post_url": "https://channels.weixin.qq.com/...",
  "error": null | "错误描述"
}
```

## Error Handling & Retry
- 扫码超时：重新生成二维码并提示用户
- 上传超时（>5分钟）：检查网络，重试 1 次
- 审核不通过：记录原因，人工处理

## Notes
⚠️ **此文件为技能定义，不包含真实 Playwright 实现代码**
- 视频号登录**必须**微信扫码，无法完全自动化，首次需人工介入
- Cookie 有效期约 7 天，过期需重新扫码
- 视频号直接打通微信，是引流效果最好的平台
- 发布后建议手动转发到微信群和朋友圈（无法自动化）
- 视频号对视频质量要求较高，建议使用原始高清版本
