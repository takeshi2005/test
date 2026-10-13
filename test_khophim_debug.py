#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script kiểm tra độc lập kết nối đến KhoPhim.org
Giúp chẩn đoán chính xác xem KhoPhim bị chặn ở đâu, mã lỗi là gì,
và phản hồi của Cloudflare như thế nào (khi có cookie vs khi không có cookie).
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

# Cấu hình thử nghiệm
TEST_TITLE = "Nghịch Thiên Kỳ Án"
TEST_SLUG = "nghich-thien-ky-an-phan-1"

# Headers giả lập trình duyệt Edge/Chrome thật
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

DEFAULT_COOKIE = (
    "cf_clearance=ivFLZN24LoRdhQarbh5acQ9IOXsGxqRVzQ3gHHKbmQw-1791894888-1.2.1.1-0OZeMRkltXgc2XF0O5bTXQ.UmlX9kR77XehQwN5pvqmLhU6SNEflB11kXWHx8eZVAVtdu5z9jcD25Jm6RSzvAiInOYeFOMOPNNKbHlhc2aUbpQwbDnackwoK.IkE_5XwNHCaiD6u8NDKjLUg1iW3QIHDCq9jmdEsxUsxxLxZBiXCU1f_TUK8n9Cj7lSPDLtk69zLUu7JJGpZKNLsSVfC9HZB_k73pZ80RPVQXZJauCWj0DeB1f_SniGguTIp5V0CePUXnoRtvsQiIdNWstXcIGiBeKhoseOC5ZD7yCg9F5ICnzLKN8VC0DDdBvEl14oo9GWP6s89a2igrcccY_DD5JO9tlg.DCHowbiLpTVZchA; "
    "_ga=GA1.1.460584032.1791894980; _ga_6B5GLB9W6H=GS2.1.s1791894980$o1$g1$t1791894989$j51$l0$h0; _ga_B3MTYDEYY3=GS2.1.s1791894980$o1$g1$t1791894989$j51$l0$h0"
)

COOKIE = os.getenv("KHOPHIM_COOKIE") or DEFAULT_COOKIE


async def test_endpoint(session: aiohttp.ClientSession, name: str, url: str, use_cookie: bool = True):
    print(f"\n{'='*70}")
    print(f"👉 [TEST] {name}")
    print(f"   URL: {url}")
    print(f"   Cookie: {'CÓ COOKIE' if use_cookie else 'KHÔNG COOKIE'}")
    print(f"{'-'*70}")

    headers = dict(BROWSER_HEADERS)
    if use_cookie and COOKIE:
        headers["Cookie"] = COOKIE

    # Nếu là endpoint chi tiết, cập nhật lại Referer
    if "movie-detail" in url:
        headers["Referer"] = f"https://khophim.org/phim/{TEST_SLUG}"

    start_time = time.time()
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
            elapsed = time.time() - start_time
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            cf_ray = resp.headers.get("cf-ray", "Không có cf-ray (Không qua Cloudflare)")
            server = resp.headers.get("server", "N/A")

            print(f"   ⏱️ Thời gian: {elapsed:.2f}s")
            print(f"   📊 HTTP Status: {status}")
            print(f"   🏷️ Content-Type: {content_type}")
            print(f"   ☁️ Cloudflare Ray: {cf_ray}")
            print(f"   🖥️ Server: {server}")

            body = await resp.text()

            # Phân tích kết quả
            if status == 200:
                if "application/json" in content_type or body.strip().startswith(("{", "[")):
                    try:
                        data = json.loads(body)
                        print("   ✅ KẾT QUẢ: Thành công (JSON hợp lệ)!")
                        if "items" in data or "data" in data:
                            items = data.get("items") or (data.get("data") or {}).get("items", [])
                            print(f"      -> Tìm thấy {len(items)} kết quả")
                            for idx, it in enumerate(items[:3]):
                                print(f"         [{idx+1}] {it.get('name')} (slug: {it.get('slug')})")
                        elif "movie" in data:
                            m = data.get("movie", {})
                            print(f"      -> Phim: {m.get('name')}")
                            print(f"      -> Mô tả: {len(m.get('content', ''))} ký tự")
                            print(f"      -> Poster: {m.get('poster_url') or m.get('thumb_url')}")
                    except Exception as e:
                        print(f"   ⚠️ Lỗi phân tích JSON: {e}")
                        print(f"   Body snippet: {body[:200]}")
                else:
                    print("   ⚠️ Trả về 200 nhưng là HTML (có thể là trang Cloudflare challenge):")
                    print(f"   {body[:300]}...")
            elif status == 403:
                print("   ❌ BỊ CHẶN 403 (Cloudflare Forbidden / Bot Block)!")
                if "cf-mitigated" in resp.headers or "just a moment" in body.lower():
                    print("   -> Bị Cloudflare bật trang kiểm tra BOT (Just a moment / Turnstile challenge).")
                print(f"   Snippet: {body[:250]}...")
            elif status == 503:
                print("   ❌ LỖI 503 (Service Unavailable / Cloudflare Under Attack mode)!")
                print(f"   Snippet: {body[:250]}...")
            else:
                print(f"   ⚠️ Mã lỗi HTTP {status}:")
                print(f"   Snippet: {body[:250]}...")

    except asyncio.TimeoutError:
        print(f"   ❌ TIMEOUT: Quá 10 giây không có phản hồi!")
    except Exception as e:
        print(f"   ❌ EXCEPTION: {type(e).__name__} - {e}")


async def main():
    print("=" * 70)
    print("🚀 BẮT ĐẦU CHẨN ĐOÁN KẾT NỐI KHOPHIM.ORG")
    print(f"Cookie hiện tại: {COOKIE[:35]}...{COOKIE[-20:] if len(COOKIE) > 55 else ''}")
    print("=" * 70)

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # 1. Thử vào trang chủ
        await test_endpoint(session, "1. Truy cập Trang chủ khophim.org", "https://khophim.org/", use_cookie=False)

        # 2. Thử Search API KHÔNG cookie
        search_url = f"https://khophim.org/api/search?q={urllib.parse.quote(TEST_TITLE)}&limit=16"
        await test_endpoint(session, "2. Gọi API Search (KHÔNG cookie)", search_url, use_cookie=False)

        # 3. Thử Search API CÓ cookie
        await test_endpoint(session, "3. Gọi API Search (CÓ cookie)", search_url, use_cookie=True)

        # 4. Thử Movie Detail API KHÔNG cookie
        detail_url = f"https://khophim.org/api/movie-detail?slug={TEST_SLUG}"
        await test_endpoint(session, "4. Gọi API Movie Detail (KHÔNG cookie)", detail_url, use_cookie=False)

        # 5. Thử Movie Detail API CÓ cookie
        await test_endpoint(session, "5. Gọi API Movie Detail (CÓ cookie)", detail_url, use_cookie=True)

    print("\n" + "=" * 70)
    print("🏁 HOÀN TẤT CHẨN ĐOÁN!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
