# Follow Builders → Folo RSS

将 [Zara Zhang 的 Follow Builders](https://github.com/zarazhangrui/follow-builders) 公开 JSON 转换为三个标准 RSS 2.0 订阅。无需模型、X API Key、服务器或额外依赖。

- `feeds/x.xml`：X 帖子，按单条帖子收录。
- `feeds/podcasts.xml`：播客及上游提供的文字稿。
- `feeds/blogs.xml`：博客。当前上游没有新文章时可以为空。

## 发布和订阅

上传本项目到公开 GitHub 仓库（不要上传 `source-cache`）。Actions 每 6 小时执行一次；第一次上传会触发运行。也可以在 Actions → Update Follow Builders RSS → Run workflow 手动运行。

在 Folo 的添加订阅入口，逐个粘贴下面的地址，把 OWNER 替换为你的 GitHub 用户名，BRANCH 替换为仓库默认分支（一般为 main）：

```
https://raw.githubusercontent.com/OWNER/follow-builders-rss/BRANCH/feeds/x.xml
https://raw.githubusercontent.com/OWNER/follow-builders-rss/BRANCH/feeds/podcasts.xml
https://raw.githubusercontent.com/OWNER/follow-builders-rss/BRANCH/feeds/blogs.xml
```

这是普通 RSS，无需 RSSHub。raw 地址由 GitHub 托管，不要求另外启用 Pages；Folo 能否拉取仍需实际添加后验证。

## 本地验证

```
python -X utf8 convert.py --cache-dir source-cache
python -X utf8 -m unittest discover -s tests -v
```

源失败时保留最后成功的 RSS；每类最多保留最近 500 条，稳定 GUID 防止重复订阅条目。公开的 state 文件只包含上游公开资讯，不包含个人收藏、笔记或账号密钥。`feeds/status.json` 记录各源更新时间和故障。

原作者和原文链接保留。转换不新增事实判断或中文 AI 摘要，不代表取得原内容的转载授权。播客链接依照上游提供的 URL，可能指向频道播放列表而非单集。

免费运行依赖 GitHub 的服务和额度政策。定时运行可能延迟；长期没有仓库活动时 GitHub 可能暂停 schedule，需要在 Actions 重新启用。已有 Codex 每日推送独立保留。
