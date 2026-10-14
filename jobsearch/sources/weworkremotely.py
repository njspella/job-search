"""We Work Remotely RSS feed (no key). Item titles look like 'Company: Job Title'."""

import email.utils
import xml.etree.ElementTree as ET

from . import get, job

URL = "https://weworkremotely.com/remote-jobs.rss"


def parse(xml_text):
    out = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        raw = item.findtext("title") or ""
        company, _, title = raw.partition(": ")
        if not title:
            company, title = "", raw
        posted = ""
        try:
            posted = email.utils.parsedate_to_datetime(item.findtext("pubDate")).date().isoformat()
        except (TypeError, ValueError):
            pass
        link = item.findtext("link") or ""
        out.append(job(
            source="weworkremotely", source_id=item.findtext("guid") or link, title=title.strip(),
            company=company.strip(), location=item.findtext("region") or "", remote=True,
            url=link, posted=posted,
        ))
    return out


def fetch(cfg):
    return parse(get(URL))
