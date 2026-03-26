---
name: upload-douyin
version: 1.0.0
description: 自动上传招工视频到抖音创作者平台
trigger: 当 upload_to_platforms() 的 platforms 包含 'douyin' 时调用
---

# Upload to 抖音

## Trigger
当主流程生成视频后，用户选择上传到抖音平台时触发。建议在快手上传后延迟 30 分钟执行。

## Inputs
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| video_path | str | ✅ | 本地视频文件绝对路径 (.mp4) |
| title | str | ✅ | 视频标题（≤55字，抖音限制） |
| description | str | ❌ | 视频描述（可含话题标签） |
| tags | list[str] | ❌ | 话题标签（抖音支持#话题格式） |
| cover_path | str | ❌ | 封面图片路径 |
| location | str | ❌ | 定位城市（提升地域流量） |

## Steps（Playwright 伪代码）

```python
# Step 1: 打开抖音创作者服务平台
browser.goto("https://creator.douyin.com/creator-micro/content/upload")

# Step 2: 验证登录状态
if not is_logged_in():
    context.add_cookies(load_cookies("douyin"))
    browser.reload()

# Step 3: 上传视频
page.locator("input[type='file']").set_input_files(video_path)
page.wait_for_selector(".upload-complete-icon", timeout=180000)

# Step 4: 填写标题和描述
page.fill(".input-title", title)
if description:
    page.fill(".input-description", description)

# Step 5: 添加话题（description 中添加 #话题 格式）
# 或通过话题搜索框添加
for tag in tags[:3]:
    page.click(".topic-btn")
    page.fill(".topic-input", tag)
    page.click(".topic-item:first-child")

# Step 6: 添加定位（可选）
if location:
    page.click(".location-btn")
    page.fill(".location-search", location)
    page.click(".location-result:first-child")

# Step 7: 选择封面（可选）
if cover_path:
    page.click(".cover-btn")
    page.locator("input.cover-input").set_input_files(cover_path)
    page.click(".cover-confirm-btn")

# Step 8: 发布
page.click(".publish-btn")
page.wait_for_url("**/content/manage**", timeout=30000)
```

## Output
```json
{
  "platform": "douyin",
  "status": "success" | "failed",
  "post_url": "https://www.douyin.com/video/...",
  "error": null | "错误描述"
}
```

## Error Handling & Retry
- 视频审核中：等待 5 分钟后检查状态，最多等 3 次
- 登录失效：停止，提示重新登录
- 上传卡住：刷新页面重试，最多 2 次

## Notes
⚠️ **此文件为技能定义，不包含真实 Playwright 实现代码**
- 抖音 DOM 结构变更频繁，选择器需定期维护
- 前 3 秒必须出现最高工资数字（内容策略）
- 不能在标题/描述中直接写微信号（用谐音或评论区引导）
- 建议发布时添加本地城市定位，提升同城流量
