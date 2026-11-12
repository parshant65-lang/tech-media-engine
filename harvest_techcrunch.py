#!/usr/bin/env python3
import os
import sys
import json
import gzip
import time
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

VAULT_REPO = "tech-media-vault-1"
GITHUB_USER = "parshant65-lang"
SOURCE_NAME = "techcrunch"
PER_PAGE = 100
MAX_PAGES_PER_RUN = 50   # 50 pages x 100 = 5,000 articles per run
PAGES_PER_FILE = 10      # 1,000 articles per compressed file (~1.9 MB)

def get_auth_remote(pat):
    return f"https://x-access-token:{pat}@github.com/{GITHUB_USER}/{VAULT_REPO}.git"

def safe_git(cmd, cwd):
    for attempt in range(3):
        try:
            return subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.STDOUT).decode().strip()
        except subprocess.CalledProcessError as e:
            err = e.output.decode() if e.output else str(e)
            print(f"[GIT-WARN] Attempt {attempt+1} failed: {err}")
            time.sleep(3)
    raise RuntimeError(f"Git command failed after 3 attempts: {' '.join(cmd)}")

def fetch_page(page_num):
    url = f"https://techcrunch.com/wp-json/wp/v2/posts?per_page={PER_PAGE}&page={page_num}&_fields=id,date,date_gmt,link,title,excerpt,content"
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}
    
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read().decode("utf-8")
                total_pages = resp.headers.get("X-WP-TotalPages")
                total_items = resp.headers.get("X-WP-Total")
                posts = json.loads(raw)
                return posts, int(total_pages) if total_pages else None, int(total_items) if total_items else None
        except urllib.error.HTTPError as e:
            if e.code == 400: # Page out of bounds
                return [], None, None
            print(f"[HTTP-WARN] Page {page_num} returned code {e.code}, retry {attempt+1}/5...")
            time.sleep(3 * (attempt + 1))
        except Exception as e:
            print(f"[NET-WARN] Page {page_num} failed: {e}, retry {attempt+1}/5...")
            time.sleep(3 * (attempt + 1))
    return None, None, None

def clean_post(p):
    title = p.get("title", {})
    t_str = title.get("rendered", "") if isinstance(title, dict) else str(title)
    
    excerpt = p.get("excerpt", {})
    e_str = excerpt.get("rendered", "") if isinstance(excerpt, dict) else str(excerpt)
    
    content = p.get("content", {})
    c_str = content.get("rendered", "") if isinstance(content, dict) else str(content)
    
    return {
        "id": p.get("id"),
        "date": p.get("date"),
        "date_gmt": p.get("date_gmt"),
        "link": p.get("link"),
        "title": t_str,
        "excerpt": e_str,
        "content": c_str
    }

def main():
    pat = os.environ.get("VAULT_PAT")
    if not pat:
        print("[ERROR] VAULT_PAT environment variable not set!")
        sys.exit(1)
        
    vault_dir = os.path.abspath("vault_work_tc")
    remote_url = get_auth_remote(pat)
    
    if os.path.exists(vault_dir):
        subprocess.run(["rm", "-rf", vault_dir])
        
    print(f"[INIT] Cloning {VAULT_REPO} (depth 1)...")
    safe_git(["git", "clone", "--depth", "1", remote_url, vault_dir], cwd=".")
    safe_git(["git", "config", "user.name", "TechMediaBot"], cwd=vault_dir)
    safe_git(["git", "config", "user.email", "bot@intelligence.internal"], cwd=vault_dir)
    
    ckpt_path = os.path.join(vault_dir, "checkpoint.json")
    if os.path.exists(ckpt_path):
        with open(ckpt_path, "r", encoding="utf-8") as f:
            ckpt = json.load(f)
    else:
        ckpt = {"source": SOURCE_NAME, "last_page": 0, "total_pages": 2633, "articles_collected": 0}

    last_page = ckpt.get("last_page", 0)
    total_pages = ckpt.get("total_pages", 2633)
    articles_collected = ckpt.get("articles_collected", 0)
    
    print(f"[STATUS] TechCrunch Current Checkpoint: Page {last_page}/{total_pages} | Articles: {articles_collected:,}")
    
    if last_page >= total_pages:
        print("[COMPLETE] TechCrunch archive is fully harvested!")
        return

    data_dir = os.path.join(vault_dir, "data", "techcrunch")
    os.makedirs(data_dir, exist_ok=True)
    
    start_page = last_page + 1
    end_page = min(last_page + MAX_PAGES_PER_RUN, total_pages)
    
    print(f"[BATCH] Harvesting Pages {start_page} to {end_page} ({end_page - start_page + 1} pages)...")
    
    curr_batch_posts = []
    curr_batch_start_page = start_page
    pages_processed = 0
    total_new_articles = 0
    
    for p in range(start_page, end_page + 1):
        t0 = time.time()
        posts, detected_pages, detected_total = fetch_page(p)
        dt = time.time() - t0
        
        if posts is None:
            print(f"[ERROR] Failed to fetch page {p} after multiple retries. Breaking batch early.")
            break
            
        if not posts:
            print(f"[INFO] Page {p} is empty. Archive end reached.")
            ckpt["total_pages"] = p - 1
            break
            
        if detected_pages:
            total_pages = detected_pages
            ckpt["total_pages"] = total_pages
            
        cleaned = [clean_post(x) for x in posts]
        curr_batch_posts.extend(cleaned)
        pages_processed += 1
        total_new_articles += len(cleaned)
        articles_collected += len(cleaned)
        ckpt["last_page"] = p
        ckpt["articles_collected"] = articles_collected
        
        print(f"  ✓ Page {p}/{total_pages}: {len(cleaned)} posts in {dt:.2f}s | Batch: {len(curr_batch_posts)} | Total: {articles_collected:,}")
        
        # Save every PAGES_PER_FILE or at end of loop
        if len(curr_batch_posts) >= (PAGES_PER_FILE * PER_PAGE) or p == end_page:
            file_name = f"pages_{curr_batch_start_page:05d}_to_{p:05d}.json.gz"
            file_path = os.path.join(data_dir, file_name)
            compressed_bytes = gzip.compress(json.dumps(curr_batch_posts, ensure_ascii=False).encode("utf-8"))
            with open(file_path, "wb") as f:
                f.write(compressed_bytes)
            print(f"[SAVED] {file_name} ({len(curr_batch_posts)} articles, {len(compressed_bytes)/1024:.1f} KB)")
            curr_batch_posts = []
            curr_batch_start_page = p + 1

    # Save remaining posts if any
    if curr_batch_posts:
        file_name = f"pages_{curr_batch_start_page:05d}_to_{ckpt['last_page']:05d}.json.gz"
        file_path = os.path.join(data_dir, file_name)
        compressed_bytes = gzip.compress(json.dumps(curr_batch_posts, ensure_ascii=False).encode("utf-8"))
        with open(file_path, "wb") as f:
            f.write(compressed_bytes)
        print(f"[SAVED] {file_name} ({len(curr_batch_posts)} articles, {len(compressed_bytes)/1024:.1f} KB)")

    ckpt["updated_at"] = datetime.utcnow().isoformat() + "Z"
    with open(ckpt_path, "w", encoding="utf-8") as f:
        json.dump(ckpt, f, indent=2)

    # Git push
    if total_new_articles > 0:
        safe_git(["git", "add", "-A"], cwd=vault_dir)
        commit_msg = f"[TC-CLOUD] Ingest pages {start_page}-{ckpt['last_page']} (+{total_new_articles:,} articles, Total Vault: {articles_collected:,}) [skip ci]"
        safe_git(["git", "commit", "-m", commit_msg], cwd=vault_dir)
        print(f"[PUSH] Pushing to {VAULT_REPO}...")
        safe_git(["git", "push", "origin", "main"], cwd=vault_dir)
        print(f"[SUCCESS] Pushed batch: {commit_msg}")
    else:
        print("[INFO] No new articles harvested.")

    # Cleanup local work dir
    subprocess.run(["rm", "-rf", vault_dir])

if __name__ == "__main__":
    main()
