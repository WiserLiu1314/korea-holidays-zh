# 韩国放假日 · 中文订阅

自动把韩国全国公休日转换成中文，提供 iPhone 可订阅的全天日历。**不与中国大陆去重**，完整保留春节、中秋、元旦、劳动节、补假与已收录的临时假日。普通周末与不放假的纪念日不加入日历；落在周末的公休日仍保留。

## 订阅

- 网页：https://WiserLiu1314.github.io/korea-holidays-zh/
- 首选 HTTPS 日历：https://WiserLiu1314.github.io/korea-holidays-zh/korea-zh.ics
- 备用日历：https://raw.githubusercontent.com/WiserLiu1314/korea-holidays-zh/main/docs/korea-zh.ics

iPhone：**日历 → 日历 → 添加日历 → 添加订阅日历**，输入上述任意一个日历地址。只订阅一个地址；关闭原来的韩文韩国节日历及旧的手动导入版以免重复。

下载 `.ics` 后手动导入不会自动更新；请使用在线订阅。所有事件为全天事件，不设提醒。iPhone 刷新订阅可能有延迟。

## 首次开启 GitHub Pages

在仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。

随后在 **Actions → 更新中文韩国假日日历 → Run workflow** 手动运行一次。`update` 作业负责更新并提交日历，`deploy` 作业负责发布 Pages。即使 Pages 尚未开启，备用日历地址仍可用。

## 自动更新

每天 UTC 22:17（韩国次日 07:17、中国次日 06:17）自动检查。GitHub 调度可能延迟；不是实时推送。

- 数据来自 [hyunbinseo/holidays-kr](https://github.com/hyunbinseo/holidays-kr)，是按韩国官方月历资料整理的 **MIT 开源第三方数据**，不是直接调用政府 API。
- 无需韩国证件、API 密钥、付费服务或翻译模型。使用固定韩中词典，未来年份只在上游提供后加入；保留2026年以来的数据。
- 主读取地址为其 GitHub 原始 JSON；故障时尝试同一项目的公开托管 JSON。两个地址属于同一数据源，不是独立交叉验证。
- 每次成功抓取都会提交数据和更新时间。这也持续产生仓库活动，降低公共仓库定时工作流因60天无活动被停用的风险，仍不保证平台永不暂停。
- 节名、格式和数据完整性验证失败时，停止生成、保留已提交日历，工作流标记失败。可以开启 GitHub Actions 的失败通知；未主动设置外部邮件或消息发送。
- 临时假日、新法律和日期修订在上游维护者收录后才能同步。如果上游停更，仍需替换数据源；无法保证永久免维护。
- 出现无法翻译的新名称时停止发布，避免中文日历遗漏或误译；补充 `scripts/update_calendar.py` 的词典即可。
- 同一天多个韩国公休日合并成一条事件并展示全部名称。每个日期有稳定 UID，重复抓取不改事件时间戳；名称变更时递增 SEQUENCE。

“补假”是额外休息日，不是周末补班。公休日安排与所在单位实际出勤安排可能不同。

## 本地运行

只需要 Python 3.10+，无第三方依赖。

```sh
python -m unittest discover -s tests -v
python scripts/update_calendar.py
```

离线重建已核对快照：`python scripts/update_calendar.py --offline`。离线模式不会获取最新数据，不用于每日工作流。

文件：`docs/korea-zh.ics`（订阅）、`docs/holidays.json`（中文日期）、`docs/status.json`（核对记录）、`data/source.json`（上游快照）、`data/events.json`（事件版本信息）。

## 授权与来源

上游数据版权及 MIT 授权见 `THIRD_PARTY_LICENSES.txt`。首次核对2026年共22个公休日日期、2027年共24个，包含2026年新增的劳动节、制宪节及2027年相应补假。

官方核对资料：[韩国宇宙航空厅2027年月历要项](https://www.kasa.go.kr/prog/plcyBrf/brief/kor/sub01_01_04/view.do?plcyBrfNo=431)、[韩国旅游发展局假日资料](https://chinese.visitkorea.or.kr/svc/contents/infoHtmlView.do?menuSn=372&vcontsId=140045)。
