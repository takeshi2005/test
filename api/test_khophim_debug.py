#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kiểm tra kết nối KhoPhim.org theo 2 đường:
  A. TRỰC TIẾP tới khophim.org (dễ bị Cloudflare chặn IP datacenter)
  B. QUA Cloudflare Worker proxy (KHOPHIM_BASE_URL)

Biến môi trường:
  KHOPHIM_BASE_URL : URL Worker (mặc định https://khophim.huuvinh-brt.workers.dev)
  KHOPHIM_COOKIE   : (tuỳ chọn) cookie, chỉ dùng cho đường trực tiếp / chuyển tiếp qua Worker
"""

import sys
import os
import time
import json
import urllib.parse
import aiohttp
import asyncio

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

TEST_TITLE = "Nghịch Thiên Kỳ Án"
TEST_SLUG = "nghich-thien-ky-an-phan-1"

DIRECT_BASE = "https://khophim.org"
PROXY_BASE = (os.getenv("KHOPHIM_BASE_URL") or "https://khophim.huuvinh-brt.workers.dev").rstrip("/")
COOKIE = os.getenv("KHOPHIM_COOKIE", "")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    "Referer": "https://khophim.org/",
    "sec-ch-ua": '"Microsoft Edge";v="155", "Chromium";v="155", "Not(A:Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "priority": "u=1, i",
}


async def test_endpoint(session, name, url, use_cookie=False):
    print(f"\n{'='*70}")
    print(f"👉 [TEST] {name}")
    print(f"   URL: {url}")
    print(f"   Cookie: {'CÓ' if (use_cookie and COOKIE) else 'KHÔNG'}")
    print(f"{'-'*70}")

    headers = dict(BROWSER_HEADERS)
    if use_cookie and COOKIE:
        headers["Cookie"] = COOKIE
    if "movie-detail" in url:
        headers["Referer"] = f"https://khophim.org/phim/{TEST_SLUG}"

    start = time.time()
    try:
        async with session.get(
            url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            elapsed = time.time() - start
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
            print(f"   ⏱️ Thời gian: {elapsed:.2f}s")
            print(f"   📊 HTTP Status: {status}")
            print(f"   🏷️ Content-Type: {ctype}")
            print(f"   ☁️ Cloudflare Ray: {resp.headers.get('cf-ray', 'N/A')}")
            print(f"   🖥️ Server: {resp.headers.get('server', 'N/A')}")

            body = await resp.text()

            if status == 200:
                if "json" in ctype or body.strip().startswith(("{", "[")):
                    try:
                        data = json.loads(body)
                        print("   ✅ Thành công (JSON hợp lệ)!")
                        if isinstance(data, dict) and data.get("status") == "ok":
                            print(f"      -> Worker hoạt động: {data.get('service')}")
                        elif isinstance(data, dict) and ("items" in data or "data" in data):
                            items = data.get("items") or (data.get("data") or {}).get("items", [])
                            print(f"      -> Tìm thấy {len(items)} kết quả")
                            for i, it in enumerate(items[:3], 1):
                                print(f"         [{i}] {it.get('name')} (slug: {it.get('slug')})")
                        elif isinstance(data, dict) and "movie" in data:
                            m = data["movie"] or {}
                            print(f"      -> Phim: {m.get('name')}")
                            print(f"      -> Mô tả: {len(m.get('content', ''))} ký tự")
                            print(f"      -> Poster: {m.get('poster_url') or m.get('thumb_url')}")
                    except Exception as e:
                        print(f"   ⚠️ Lỗi phân tích JSON: {e}\n   Body: {body[:200]}")
                else:
                    print("   ⚠️ 200 nhưng là HTML (có thể là trang challenge):")
                    print(f"   {body[:300]}...")
            elif status == 403:
                print("   ❌ BỊ CHẶN 403!")
                if "cf-mitigated" in resp.headers or "just a moment" in body.lower():
                    print("   -> Cloudflare bật trang kiểm tra BOT (Just a moment / Turnstile).")
                print(f"   Snippet: {body[:250]}...")
            elif status == 502:
                print("   ❌ 502 từ Worker (Worker không fetch được khophim.org):")
                print(f"   {body[:250]}")
            else:
                print(f"   ⚠️ HTTP {status}: {body[:250]}...")
    except asyncio.TimeoutError:
        print("   ❌ TIMEOUT: quá 15 giây không phản hồi!")
    except Exception as e:
        print(f"   ❌ EXCEPTION: {type(e).__name__} - {e}")


async def main():
    print("=" * 70)
    print("🚀 CHẨN ĐOÁN KẾT NỐI KHOPHIM.ORG")
    print(f"Proxy Worker : {PROXY_BASE}")
    print(f"Cookie       : {'có (%d ký tự)' % len(COOKIE) if COOKIE else 'không'}")
    print("=" * 70)

    q = urllib.parse.quote(TEST_TITLE)
    search_path = f"/api/search?q={q}&limit=16"
    detail_path = f"/api/movie-detail?slug={TEST_SLUG}"

    async with aiohttp.ClientSession() as session:
        print("\n######## A. QUA WORKER PROXY ########")
        await test_endpoint(session, "A0. Health check Worker", f"{PROXY_BASE}/health")
        await test_endpoint(session, "A1. Search qua Worker", PROXY_BASE + search_path)
        await test_endpoint(session, "A2. Movie Detail qua Worker", PROXY_BASE + detail_path)

        print("\n######## B. TRỰC TIẾP (đối chứng) ########")
        await test_endpoint(session, "B1. Search trực tiếp (không cookie)", DIRECT_BASE + search_path)
        if COOKIE:
            await test_endpoint(session, "B2. Search trực tiếp (có cookie)", DIRECT_BASE + search_path, use_cookie=True)
        await test_endpoint(session, "B3. Movie Detail trực tiếp (không cookie)", DIRECT_BASE + detail_path)

    print("\n" + "=" * 70)
    print("🏁 HOÀN TẤT!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
