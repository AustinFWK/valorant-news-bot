from scraper import get_latest_patch_notes, get_latest_article_url, is_youtube_link

# --- Test URL Detection ---
print("=" * 50)
print("Testing is_youtube_link()")
print("=" * 50)

test_urls = [
    ("https://youtube.com/watch?v=abc123", True),
    ("https://www.youtube.com/watch?v=abc123", True),
    ("https://youtu.be/abc123", True),
    ("https://playvalorant.com/en-us/news/game-updates/", False),
    ("https://playvalorant.com/en-us/news/patch-notes-10-01/", False),
]

all_passed = True
for url, expected in test_urls:
    result = is_youtube_link(url)
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_passed = False
    print(f"  {status} is_youtube_link('{url[:40]}...') = {result}")

print(f"\nURL detection tests: {'All passed!' if all_passed else 'Some failed!'}")


# --- Test Live Scraper ---
print("\n" + "=" * 50)
print("Testing get_latest_patch_notes() - LIVE")
print("=" * 50)
print("(This will open a Chrome window briefly)\n")

try:
    text_content, url, content_type = get_latest_patch_notes()

    print(f"  URL: {url}")
    print(f"  Type: {content_type}")

    if content_type == 'video':
        print("  Content: N/A (video link)")
    elif text_content:
        preview = text_content[:300].replace('\n', ' ')
        print(f"  Content preview: {preview}...")
    else:
        print("  Content: Empty (unexpected!)")

    print("\n✅ Scraper executed successfully!")

except Exception as e:
    print(f"\n❌ Scraper failed with error: {e}")


# --- Test Article URL Fetcher ---
print("\n" + "=" * 50)
print("Testing get_latest_article_url() - LIVE")
print("=" * 50)

try:
    url = get_latest_article_url()
    print(f"  Latest URL: {url}")
    print("\n✅ URL fetcher executed successfully!")
except Exception as e:
    print(f"\n❌ URL fetcher failed with error: {e}")


# --- Test Formatter Output ---                                                                                        
from valorant.formatter import smart_chunk                                                                             
                                                                                                                         
print("\n" + "=" * 50)
print("Testing smart_chunk() with live HTML")
print("=" * 50)

try:
      html_content, url, content_type = get_latest_patch_notes()

      if content_type == 'article' and html_content:
          chunks = smart_chunk(html_content)
          print(f"  Produced {len(chunks)} chunk(s)\n")
          for i, chunk in enumerate(chunks, 1):
              print(f"--- Chunk {i} ---")
              print(chunk)
              print()
      else:
          print("  Skipped (video or no content)")

      print("✅ Formatter executed successfully!")

except Exception as e:
      print(f"❌ Formatter failed: {e}")
