#!/usr/bin/env python3
"""Generate a Chinese all-day calendar from the public holidays-kr dataset."""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PROJECT = "https://github.com/hyunbinseo/holidays-kr"
SOURCES = [
    "https://raw.githubusercontent.com/hyunbinseo/holidays-kr/main/public/basic.json",
    "https://holidays.hyunbin.page/basic.json",
]
BASE_URL = "https://WiserLiu1314.github.io/korea-holidays-zh"
RAW_URL = "https://raw.githubusercontent.com/WiserLiu1314/korea-holidays-zh/main/docs/korea-zh.ics"
TRANSLATIONS = {
    "1월 1일": "元旦", "신정": "元旦", "새해": "元旦",
    "설날": "春节", "설날 전날": "春节假期（除夕）",
    "설날 다음 날": "春节假期（次日）", "설날 다음날": "春节假期（次日）",
    "3ㆍ1절": "三一节", "3·1절": "三一节", "삼일절": "三一节",
    "노동절": "劳动节", "근로자의 날": "劳动节",
    "어린이날": "儿童节", "부처님 오신 날": "佛诞节",
    "부처님오신날": "佛诞节", "석가탄신일": "佛诞节",
    "현충일": "显忠日", "제헌절": "制宪节", "광복절": "光复节",
    "추석": "中秋节（秋夕）", "추석 전날": "中秋假期（前日）",
    "추석 다음 날": "中秋假期（次日）", "추석 다음날": "中秋假期（次日）",
    "개천절": "开天节", "한글날": "韩文日", "기독탄신일": "圣诞节",
    "성탄절": "圣诞节", "크리스마스": "圣诞节",
    "전국동시지방선거": "全国地方选举日", "대통령선거": "总统选举日",
    "임시공휴일": "临时公休日", "대체공휴일": "补假",
}


def translate(name):
    name = re.sub(r"\s+", " ", name.strip()).replace("（", "(").replace("）", ")")
    if name in TRANSLATIONS:
        return TRANSLATIONS[name]
    match = re.fullmatch(r"(대체\s*공휴일|임시\s*공휴일)\s*\((.+)\)", name)
    if match:
        inner = translate(match[2])
        if match[1].replace(" ", "") == "대체공휴일":
            return inner + "补假"
        return "临时公休日（" + inner + "）"
    if re.fullmatch(r"제\s*\d+\s*대\s*국회의원\s*선거", name):
        return "国会议员选举日"
    if re.fullmatch(r"제\s*\d+\s*대\s*대통령\s*선거", name):
        return "总统选举日"
    if re.fullmatch(r"제\s*\d+\s*회\s*전국동시지방선거", name):
        return "全国地方选举日"
    raise ValueError(f"未识别的新节名：{name!r}。请补充中文对照后重试；保留上一版日历。")


def normalize(payload, current_year=None):
    current_year = current_year or date.today().year
    if not isinstance(payload, dict) or not payload:
        raise ValueError("上游数据不是非空年份对象")
    result = {}
    for year, days in payload.items():
        if not isinstance(year, str) or not re.fullmatch(r"20\d\d", year):
            raise ValueError("年份格式错误")
        if int(year) < 2026:
            continue
        if not isinstance(days, dict) or not 15 <= len(days) <= 45:
            raise ValueError(f"{year} 假日数量异常：应有15—45个公休日日期")
        for day, names in sorted(days.items()):
            if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                raise ValueError("日期格式错误")
            parsed = date.fromisoformat(day)
            if str(parsed.year) != year:
                raise ValueError("日期与年份不一致")
            if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n.strip() for n in names):
                raise ValueError("节名列表错误")
            result[day] = list(dict.fromkeys(translate(n) for n in names))
        if f"{year}-01-01" not in days or f"{year}-12-25" not in days:
            raise ValueError(f"{year} 缺少基础公休日，数据可能不完整")
    if not any(day.startswith(str(current_year)) for day in result):
        raise ValueError(f"上游尚未提供当前年份 {current_year}，保留上一版日历")
    return result


def fetch_source():
    errors = []
    for url in SOURCES:
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "korea-holidays-zh/1.0", "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=25) as response:
                    body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise ValueError("上游文件过大")
                payload = json.loads(body.decode("utf-8-sig"))
                normalize(payload)
                return payload, url
            except (OSError, ValueError) as exc:
                errors.append(f"{url}: {exc}")
                if attempt == 0:
                    time.sleep(2)
    raise RuntimeError("所有公开来源获取或验证失败；不改写已发布文件。\n" + "\n".join(errors))


def escape_ics(value):
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def fold_line(value):
    parts, part = [], ""
    for char in value:
        if len((part + char).encode("utf-8")) > 75:
            parts.append(part)
            part = " " + char
        else:
            part += char
    parts.append(part)
    return "\r\n".join(parts)


def build_calendar(days, old_state, now):
    state = {}
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//korea-holidays-zh//Chinese Korean Holidays//CN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:韩国放假日（中文）",
             "X-WR-TIMEZONE:Asia/Seoul", "REFRESH-INTERVAL;VALUE=DURATION:P1D", "X-PUBLISHED-TTL:P1D",
             "X-WR-CALDESC:" + escape_ics("韩国全国公休日与补假；中文显示，不与中国大陆去重。只列假日，不列普通周末。不设提醒。资料来自按官方月历整理的第三方开源数据。")]
    for day, names in sorted(days.items()):
        summary = "韩国·" + " / ".join(names)
        description = "韩国全国公休日（放假）。"
        if any("补假" in n for n in names):
            description += "补假是额外休息日，不是周末补班。"
        description += "\n不与中国大陆节日去重；普通周末不另列。\n数据源：hyunbinseo/holidays-kr，按韩国官方月历资料整理。\n临时假日和法规调整在上游收录后同步。"
        fingerprint = hashlib.sha256((summary + description).encode()).hexdigest()
        previous = old_state.get(day, {})
        unchanged = previous.get("fingerprint") == fingerprint
        modified = previous.get("modified", now) if unchanged else now
        sequence = previous.get("sequence", 0) + (0 if unchanged or not previous else 1)
        created = previous.get("created", now)
        state[day] = {"fingerprint": fingerprint, "modified": modified, "created": created, "sequence": sequence}
        d = date.fromisoformat(day)
        lines.extend(["BEGIN:VEVENT", "UID:kr-" + day.replace("-", "") + "@korea-holidays-zh",
                      "DTSTAMP:" + modified, "CREATED:" + created, "LAST-MODIFIED:" + modified,
                      "SEQUENCE:" + str(sequence), "DTSTART;VALUE=DATE:" + d.strftime("%Y%m%d"),
                      "DTEND;VALUE=DATE:" + (d + timedelta(days=1)).strftime("%Y%m%d"),
                      "SUMMARY:" + escape_ics(summary), "DESCRIPTION:" + escape_ics(description),
                      "URL:" + SOURCE_PROJECT, "TRANSP:TRANSPARENT", "STATUS:CONFIRMED", "END:VEVENT"])
    lines.append("END:VCALENDAR")
    return ("\r\n".join(fold_line(line) for line in lines) + "\r\n").encode("utf-8"), state


def make_page(days, status):
    years = sorted({d[:4] for d in days})
    sections = []
    for year in years:
        rows = []
        for day, names in sorted(days.items()):
            if day.startswith(year):
                weekday = "一二三四五六日"[date.fromisoformat(day).weekday()]
                rows.append(f'<tr><td>{day}　周{weekday}</td><td>{html.escape(" / ".join(names))}</td><td><span class="pill">休</span></td></tr>')
        sections.append(f'<section><h2>{year} 年 <small>{len(rows)} 个假日日期</small></h2><table><thead><tr><th>日期</th><th>假日</th><th>安排</th></tr></thead><tbody>{"".join(rows)}</tbody></table></section>')
    checked = html.escape(status["last_successful_fetch"])
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light"><title>韩国放假日 · 中文订阅</title>
<style>
:root{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;color:#192b35;background:#f4f6f5}}*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:900px;margin:auto;padding:56px 22px}}.tag{{color:#306d58;font-size:13px;letter-spacing:.12em}}h1{{font-size:clamp(30px,6vw,48px);letter-spacing:-.04em;margin:14px 0}}p{{line-height:1.8;color:#536570}}.lead{{font-size:17px;max-width:650px}}.actions{{display:flex;flex-wrap:wrap;gap:12px;margin:28px 0 16px}}.button{{display:inline-block;padding:13px 20px;border-radius:10px;text-decoration:none;background:#24694e;color:white;border:0;font:inherit;cursor:pointer}}.secondary{{background:white;color:#24694e;border:1px solid #ccd9d1}}.address{{padding:14px;background:white;border-radius:10px;overflow-wrap:anywhere;font-size:13px;border:1px solid #e1e8e2}}.note{{font-size:13px}}section{{background:white;border:1px solid #e1e8e2;border-radius:16px;padding:22px;margin-top:24px}}h2{{font-size:22px;margin:0 0 20px}}small{{font-size:12px;font-weight:400;color:#677b72;margin-left:10px}}table{{width:100%;border-collapse:collapse;font-size:14px}}th{{text-align:left;font-size:12px;color:#6e7c83;font-weight:500}}td,th{{padding:12px 5px;border-bottom:1px solid #edf1ee}}td:first-child{{white-space:nowrap}}.pill{{background:#eaf3ec;color:#27644b;padding:3px 8px;border-radius:5px}}a{{color:#24694e}}footer{{margin-top:28px;font-size:12px;color:#728178}}details{{margin-top:22px}}summary{{cursor:pointer}}@media(max-width:500px){{main{{padding:34px 14px}}section{{padding:16px 10px}}td,th{{font-size:12px}}small{{display:block;margin:6px 0}}}}
</style></head><body><main>
<div class="tag">KOREA / HOLIDAYS</div><h1>韩国放假日，中文看。</h1>
<p class="lead">全国公休日、补假和已收录的临时假日。全部中文显示，保留韩国完整安排，不与中国大陆去重。</p>
<div class="actions"><a class="button" href="webcal://WiserLiu1314.github.io/korea-holidays-zh/korea-zh.ics">在 iPhone 上订阅</a><button class="button secondary" id="copy">复制订阅地址</button><a class="button secondary" href="korea-zh.ics" download>下载日历</a></div>
<div class="address" id="url">{BASE_URL}/korea-zh.ics</div><p class="note" id="message" aria-live="polite">订阅一次即可。下载导入版不会自动更新；请优先选择订阅。</p>
<p class="note">最近成功核对：<time id="checked" datetime="{checked}">{checked}</time> · 每天自动检查上游。<br>已覆盖：{'、'.join(years)} 年。未公布年份不推算；临时调整在上游收录后同步。</p>
<details><summary>如何添加与理解补假</summary><p>iPhone：日历 → 日历 → 添加日历 → 添加订阅日历，粘贴上面的 HTTPS 地址。若已有韩文韩国日历或旧的手动导入版，请取消勾选它们，避免重复显示。</p><p>“补假”是额外休息日，不是周末补班。普通周末不会单独列出，但落在周末的公休日仍保留。所有事件为全天事件，默认不设置提醒。具体出勤安排以所在单位为准。</p><p>备用订阅地址：<a href="{RAW_URL}">GitHub 原始日历文件</a>。两个地址的内容相同，只需订阅其中一个。</p></details>
{''.join(sections)}
<footer>数据：<a href="{SOURCE_PROJECT}">hyunbinseo/holidays-kr</a>（MIT，按韩国官方月历整理的第三方数据） · <a href="https://github.com/WiserLiu1314/korea-holidays-zh">项目与更新记录</a>。抓取或验证失败时保留上一版。</footer>
</main><script>
document.getElementById('copy').onclick=async()=>{{try{{await navigator.clipboard.writeText(document.getElementById('url').textContent);document.getElementById('message').textContent='已复制，请粘贴到“添加订阅日历”。'}}catch(e){{document.getElementById('message').textContent='请长按上方地址手动复制。'}}}};
const t=document.getElementById('checked');t.textContent=new Date(t.dateTime).toLocaleString('zh-CN',{{timeZone:'Asia/Seoul',hour12:false}})+'（韩国时间）';
</script></body></html>'''


def update(offline=False):
    source_path = ROOT / "data/source.json"
    if offline:
        payload = json.loads(source_path.read_text())
        source_url = SOURCES[0]
    else:
        payload, source_url = fetch_source()
    days = normalize(payload)
    state_path = ROOT / "data/events.json"
    old_state = json.loads(state_path.read_text()) if state_path.exists() else {}
    old_years = {d[:4] for d in old_state}
    if not old_years.issubset({d[:4] for d in days}):
        raise ValueError("上游缺少此前已有的年份；保留上一版，需核查数据源")
    now = datetime.now(timezone.utc)
    ics, state = build_calendar(days, old_state, now.strftime("%Y%m%dT%H%M%SZ"))
    status = {"last_successful_fetch": now.isoformat(timespec="seconds"), "source_project": SOURCE_PROJECT,
              "source_url": source_url, "mode": "verified-snapshot" if offline else "live",
              "years": sorted({int(d[:4]) for d in days}), "holiday_dates": len(days)}
    outputs = {
        source_path: (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode(),
        state_path: (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode(),
        ROOT / "docs/korea-zh.ics": ics,
        ROOT / "docs/holidays.json": (json.dumps(days, ensure_ascii=False, indent=2) + "\n").encode(),
        ROOT / "docs/status.json": (json.dumps(status, ensure_ascii=False, indent=2) + "\n").encode(),
        ROOT / "docs/index.html": make_page(days, status).encode(),
        ROOT / "docs/.nojekyll": b"",
    }
    # Every validation and rendering step above completes before any file changes.
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
    print(f"已生成 {len(days)} 个假日日期；年份：{status['years']}；模式：{status['mode']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="用已核对快照离线生成（不用于每日更新）")
    args = parser.parse_args()
    try:
        update(args.offline)
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
