#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音热歌榜 -> 网易云音乐歌单自动同步

默认策略：
1. 抓取抖音热歌榜 Top N
2. 在网易云按歌曲名 + 歌手搜索
3. 用歌名、歌手、时长和版本词进行匹配
4. 读取目标歌单已有曲目
5. 只新增，不删除掉榜歌曲
6. 低置信度结果跳过，不乱加
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import secrets
import string
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests
from Cryptodome.Cipher import AES


DOUYIN_CHART_URL = "https://aweme.snssdk.com/aweme/v1/chart/music/list/"
DOUYIN_CHART_ID = "6853972723954146568"

NETEASE_BASE_URL = "https://music.163.com"
NETEASE_MODULUS = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7"
    "b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280"
    "104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932"
    "575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b"
    "3ece0462db0a22b8e7"
)
NETEASE_PUBKEY = "010001"
NETEASE_NONCE = b"0CoJUm6Qyw8W8jud"
NETEASE_IV = b"0102030405060708"

VERSION_WORDS = (
    "dj",
    "remix",
    "伴奏",
    "纯音乐",
    "翻唱",
    "cover",
    "live",
    "现场",
    "加速",
    "spedup",
    "慢速",
    "slowed",
    "片段",
    "剪辑版",
    "抖音版",
    "女版",
    "男版",
    "降调",
    "升调",
    "伴奏版",
)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def clamp_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value or default)
    except ValueError:
        number = default
    return max(minimum, min(maximum, number))


def clamp_float(value: str | None, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value or default)
    except ValueError:
        number = default
    return max(minimum, min(maximum, number))


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", str(value)).lower()
    value = unquote(value)
    value = value.replace("&", "and")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value)


def clean_query_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", str(value)).strip()
    value = re.sub(r"\s+", " ", value)
    return value[:120]


def similarity(a: str, b: str) -> float:
    a_n, b_n = normalize_text(a), normalize_text(b)
    if not a_n or not b_n:
        return 0.0
    if a_n == b_n:
        return 1.0
    return SequenceMatcher(None, a_n, b_n).ratio()


def version_penalty(source_title: str, candidate_title: str) -> float:
    source = normalize_text(source_title)
    candidate = normalize_text(candidate_title)
    penalty = 0.0
    for word in VERSION_WORDS:
        token = normalize_text(word)
        if token and token in candidate and token not in source:
            penalty += 0.08
    return min(0.32, penalty)


def extract_csrf(cookie: str) -> str:
    match = re.search(r"(?:^|;\s*)__csrf=([^;]+)", cookie)
    return match.group(1) if match else ""


def aes_encrypt(data: bytes, key: bytes) -> bytes:
    pad = 16 - len(data) % 16
    padded = data + bytes([pad] * pad)
    cipher = AES.new(key, AES.MODE_CBC, NETEASE_IV)
    return base64.b64encode(cipher.encrypt(padded))


def rsa_encrypt(secret: bytes) -> str:
    reversed_secret = secret[::-1]
    value = pow(
        int(binascii.hexlify(reversed_secret), 16),
        int(NETEASE_PUBKEY, 16),
        int(NETEASE_MODULUS, 16),
    )
    return format(value, "x").zfill(256)


def weapi_encrypt(payload: dict[str, Any]) -> dict[str, str]:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    secret = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(16)
    ).encode("ascii")
    first = aes_encrypt(data, NETEASE_NONCE)
    second = aes_encrypt(first, secret)
    return {
        "params": second.decode("ascii"),
        "encSecKey": rsa_encrypt(secret),
    }


@dataclass
class DouyinSong:
    rank: int
    douyin_id: str
    title: str
    artist: str
    duration_ms: int | None = None


@dataclass
class MatchResult:
    rank: int
    douyin_title: str
    douyin_artist: str
    netease_id: int | None
    netease_title: str | None
    netease_artist: str | None
    score: float
    status: str
    reason: str


class DouyinClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "okhttp3",
                "Accept": "application/json",
            }
        )

    def fetch_hot_music(self, limit: int) -> list[DouyinSong]:
        params = {
            "device_platform": "android",
            "version_name": "13.2.0",
            "version_code": "130200",
            "aid": "1128",
            "chart_id": DOUYIN_CHART_ID,
            "count": str(max(limit, 100)),
        }
        response = self.session.get(
            DOUYIN_CHART_URL,
            params=params,
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()

        raw_list = payload.get("music_list") or payload.get("data") or []
        songs: list[DouyinSong] = []

        for idx, wrapper in enumerate(raw_list[:limit], start=1):
            info = wrapper.get("music_info") if isinstance(wrapper, dict) else None
            if not isinstance(info, dict):
                info = wrapper if isinstance(wrapper, dict) else {}

            title = clean_query_text(info.get("title"))
            artist = clean_query_text(
                info.get("author")
                or info.get("author_name")
                or info.get("artist")
                or ""
            )
            if not title:
                continue

            duration = info.get("duration")
            try:
                duration_ms = int(duration) if duration is not None else None
            except (TypeError, ValueError):
                duration_ms = None

            songs.append(
                DouyinSong(
                    rank=idx,
                    douyin_id=str(info.get("id") or info.get("mid") or ""),
                    title=title,
                    artist=artist,
                    duration_ms=duration_ms,
                )
            )

        if not songs:
            raise RuntimeError("抖音热歌接口返回成功，但没有解析到歌曲")
        return songs


class NeteaseClient:
    def __init__(self, cookie: str) -> None:
        if not cookie.strip():
            raise ValueError("NETEASE_COOKIE 为空")
        self.cookie = cookie.strip()
        self.csrf = extract_csrf(self.cookie)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36"
                ),
                "Referer": "https://music.163.com/",
                "Origin": "https://music.163.com",
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": self.cookie,
            }
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = dict(payload)
        body["csrf_token"] = self.csrf
        response = self.session.post(
            f"{NETEASE_BASE_URL}{path}",
            data=weapi_encrypt(body),
            timeout=25,
        )
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"网易云接口没有返回 JSON：{response.text[:180]}"
            ) from exc
        return data

    def search(self, keyword: str, limit: int = 12) -> list[dict[str, Any]]:
        data = self._post(
            "/weapi/cloudsearch/get/web",
            {
                "s": keyword,
                "type": 1,
                "limit": limit,
                "offset": 0,
                "total": "true",
            },
        )
        if data.get("code") not in (200, None):
            raise RuntimeError(f"网易云搜索失败：{data}")
        return (data.get("result") or {}).get("songs") or []

    def playlist_track_ids(self, playlist_id: str) -> set[int]:
        data = self._post(
            "/weapi/v3/playlist/detail",
            {
                "id": playlist_id,
                "total": "true",
                "limit": 10000,
                "n": 10000,
                "offset": 0,
            },
        )
        if data.get("code") != 200:
            raise RuntimeError(
                "读取网易云歌单失败。请检查 NETEASE_COOKIE 是否有效、"
                "NETEASE_PLAYLIST_ID 是否正确，以及该账号是否有歌单权限。"
                f" 返回：{data}"
            )

        playlist = data.get("playlist") or {}
        result: set[int] = set()

        for item in playlist.get("trackIds") or []:
            try:
                result.add(int(item.get("id")))
            except (TypeError, ValueError, AttributeError):
                pass

        for item in playlist.get("tracks") or []:
            try:
                result.add(int(item.get("id")))
            except (TypeError, ValueError, AttributeError):
                pass

        return result

    def add_tracks(self, playlist_id: str, track_ids: list[int]) -> tuple[list[int], list[int]]:
        added: list[int] = []
        failed: list[int] = []

        # 小批量提交；如果整批失败，再逐首重试，避免一首异常拖累全部。
        for start in range(0, len(track_ids), 20):
            batch = track_ids[start : start + 20]
            data = self._post(
                "/weapi/playlist/manipulate/tracks",
                {
                    "op": "add",
                    "pid": playlist_id,
                    "trackIds": json.dumps(batch),
                    "imme": "true",
                },
            )
            if data.get("code") == 200:
                added.extend(batch)
                continue

            for track_id in batch:
                one = self._post(
                    "/weapi/playlist/manipulate/tracks",
                    {
                        "op": "add",
                        "pid": playlist_id,
                        "trackIds": json.dumps([track_id]),
                        "imme": "true",
                    },
                )
                if one.get("code") == 200:
                    added.append(track_id)
                else:
                    failed.append(track_id)
                time.sleep(0.25)

        return added, failed


def candidate_artists(song: dict[str, Any]) -> list[str]:
    artists = song.get("ar") or song.get("artists") or []
    names: list[str] = []
    for artist in artists:
        if isinstance(artist, dict) and artist.get("name"):
            names.append(str(artist["name"]))
        elif isinstance(artist, str):
            names.append(artist)
    return names


def candidate_duration(song: dict[str, Any]) -> int | None:
    value = song.get("dt")
    if value is None:
        value = song.get("duration")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def score_candidate(source: DouyinSong, candidate: dict[str, Any]) -> tuple[float, dict[str, float]]:
    candidate_title = str(candidate.get("name") or "")
    artists = candidate_artists(candidate)
    joined_artists = " / ".join(artists)

    title_score = similarity(source.title, candidate_title)
    artist_score = 0.0
    if source.artist and artists:
        artist_score = max(similarity(source.artist, artist) for artist in artists)
        artist_score = max(artist_score, similarity(source.artist, joined_artists))
    elif not source.artist:
        artist_score = 0.65

    source_duration = source.duration_ms
    target_duration = candidate_duration(candidate)
    duration_score = 0.0
    has_duration = bool(source_duration and target_duration)
    if has_duration:
        diff = abs(int(source_duration) - int(target_duration))
        if diff <= 2500:
            duration_score = 1.0
        elif diff <= 5000:
            duration_score = 0.85
        elif diff <= 10000:
            duration_score = 0.55
        elif diff <= 20000:
            duration_score = 0.2

    if has_duration:
        score = title_score * 0.66 + artist_score * 0.24 + duration_score * 0.10
    else:
        score = title_score * 0.74 + artist_score * 0.26

    score -= version_penalty(source.title, candidate_title)

    # 歌名很像但歌手完全不对时，主动降权，避免同名歌误加。
    if source.artist and artist_score < 0.18:
        score -= 0.16

    # 歌名本身差异过大，不能仅靠歌手相同通过。
    if title_score < 0.56:
        score -= 0.18

    score = max(0.0, min(1.0, score))
    return score, {
        "title": round(title_score, 4),
        "artist": round(artist_score, 4),
        "duration": round(duration_score, 4),
    }


def best_match(
    netease: NeteaseClient,
    source: DouyinSong,
    threshold: float,
) -> tuple[dict[str, Any] | None, float, dict[str, float]]:
    keyword = clean_query_text(f"{source.title} {source.artist}".strip())
    candidates = netease.search(keyword, limit=12)

    if not candidates and source.artist:
        candidates = netease.search(source.title, limit=12)

    best: dict[str, Any] | None = None
    best_score = -1.0
    best_parts: dict[str, float] = {}

    for candidate in candidates:
        score, parts = score_candidate(source, candidate)
        if score > best_score:
            best = candidate
            best_score = score
            best_parts = parts

    if best is None or best_score < threshold:
        return None, max(0.0, best_score), best_parts
    return best, best_score, best_parts


def write_report(report: dict[str, Any]) -> None:
    Path("sync_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = report["summary"]
    lines = [
        "# 抖音热歌 → 网易云同步报告",
        "",
        f"- 抖音榜单读取：{summary['fetched']} 首",
        f"- 成功匹配：{summary['matched']} 首",
        f"- 歌单已存在：{summary['already_exists']} 首",
        f"- 本次新增：{summary['added']} 首",
        f"- 低置信度跳过：{summary['skipped']} 首",
        f"- 写入失败：{summary['failed']} 首",
        f"- Dry run：{summary['dry_run']}",
        "",
        "## 明细",
        "",
        "| 排名 | 抖音歌曲 | 抖音歌手 | 网易云匹配 | 分数 | 状态 |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]

    for item in report["items"]:
        netease_text = ""
        if item["netease_title"]:
            netease_text = f"{item['netease_title']} - {item['netease_artist'] or ''}"
        lines.append(
            f"| {item['rank']} | {item['douyin_title']} | "
            f"{item['douyin_artist']} | {netease_text} | "
            f"{item['score']:.3f} | {item['status']} |"
        )

    markdown = "\n".join(lines) + "\n"
    Path("sync_report.md").write_text(markdown, encoding="utf-8")

    github_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary:
        with open(github_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown)


def main() -> int:
    cookie = os.getenv("NETEASE_COOKIE", "").strip()
    playlist_id = os.getenv("NETEASE_PLAYLIST_ID", "18422386676").strip()
    top_n = clamp_int(os.getenv("TOP_N"), 50, 1, 100)
    threshold = clamp_float(os.getenv("MATCH_THRESHOLD"), 0.68, 0.50, 0.95)
    dry_run = env_bool("DRY_RUN", False)

    if not cookie:
        print("❌ 缺少 NETEASE_COOKIE")
        return 2
    if not playlist_id.isdigit():
        print("❌ 缺少有效的 NETEASE_PLAYLIST_ID（应为纯数字歌单 ID）")
        return 2

    print(f"🎵 开始同步：抖音 Top {top_n} -> 网易云歌单 {playlist_id}")
    print(f"🎯 匹配阈值：{threshold:.2f} | DRY_RUN={dry_run}")

    douyin = DouyinClient()
    netease = NeteaseClient(cookie)

    try:
        songs = douyin.fetch_hot_music(top_n)
    except Exception as exc:
        print(f"❌ 抖音热歌榜获取失败：{exc}")
        return 3

    try:
        existing_ids = netease.playlist_track_ids(playlist_id)
    except Exception as exc:
        print(f"❌ 网易云歌单读取失败：{exc}")
        return 4

    print(f"📥 抖音榜单读取 {len(songs)} 首")
    print(f"📚 目标网易云歌单当前有 {len(existing_ids)} 个曲目 ID")

    items: list[MatchResult] = []
    pending_ids: list[int] = []
    pending_seen: set[int] = set()

    matched_count = 0
    existing_count = 0
    skipped_count = 0

    for source in songs:
        try:
            candidate, score, parts = best_match(netease, source, threshold)
        except Exception as exc:
            items.append(
                MatchResult(
                    rank=source.rank,
                    douyin_title=source.title,
                    douyin_artist=source.artist,
                    netease_id=None,
                    netease_title=None,
                    netease_artist=None,
                    score=0.0,
                    status="搜索失败",
                    reason=str(exc),
                )
            )
            skipped_count += 1
            print(f"⚠️ #{source.rank} {source.title}：搜索失败 {exc}")
            time.sleep(0.35)
            continue

        if candidate is None:
            items.append(
                MatchResult(
                    rank=source.rank,
                    douyin_title=source.title,
                    douyin_artist=source.artist,
                    netease_id=None,
                    netease_title=None,
                    netease_artist=None,
                    score=round(score, 4),
                    status="跳过",
                    reason=f"低于阈值；评分细项={parts}",
                )
            )
            skipped_count += 1
            print(
                f"⏭️ #{source.rank} {source.title} - {source.artist} "
                f"匹配不足 ({score:.3f})"
            )
            time.sleep(0.35)
            continue

        matched_count += 1
        netease_id = int(candidate["id"])
        netease_title = str(candidate.get("name") or "")
        netease_artist = " / ".join(candidate_artists(candidate))

        if netease_id in existing_ids:
            status = "已存在"
            existing_count += 1
        elif netease_id in pending_seen:
            status = "榜内重复"
            existing_count += 1
        else:
            status = "待新增"
            pending_ids.append(netease_id)
            pending_seen.add(netease_id)

        items.append(
            MatchResult(
                rank=source.rank,
                douyin_title=source.title,
                douyin_artist=source.artist,
                netease_id=netease_id,
                netease_title=netease_title,
                netease_artist=netease_artist,
                score=round(score, 4),
                status=status,
                reason=f"评分细项={parts}",
            )
        )
        print(
            f"✅ #{source.rank} {source.title} - {source.artist} -> "
            f"{netease_title} - {netease_artist} ({score:.3f}) [{status}]"
        )
        time.sleep(0.35)

    added_ids: list[int] = []
    failed_ids: list[int] = []

    if pending_ids and not dry_run:
        try:
            added_ids, failed_ids = netease.add_tracks(playlist_id, pending_ids)
        except Exception as exc:
            print(f"❌ 写入网易云歌单时发生异常：{exc}")
            failed_ids = list(pending_ids)
    elif dry_run:
        print(f"🧪 DRY_RUN：本应新增 {len(pending_ids)} 首，本次不实际写入")

    added_set = set(added_ids)
    failed_set = set(failed_ids)

    for item in items:
        if item.netease_id in added_set:
            item.status = "已新增"
        elif item.netease_id in failed_set:
            item.status = "写入失败"
        elif dry_run and item.status == "待新增":
            item.status = "DryRun待新增"

    report = {
        "summary": {
            "fetched": len(songs),
            "matched": matched_count,
            "already_exists": existing_count,
            "pending": len(pending_ids),
            "added": len(added_ids) if not dry_run else 0,
            "skipped": skipped_count,
            "failed": len(failed_ids),
            "dry_run": dry_run,
            "top_n": top_n,
            "threshold": threshold,
            "playlist_id": playlist_id,
        },
        "items": [asdict(item) for item in items],
    }
    write_report(report)

    print("")
    print("📊 同步完成")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))

    if failed_ids:
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
