import requests
from bs4 import BeautifulSoup

def dump_post(url, filename):
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
    with open(filename, 'w') as f:
        f.write(res.text)

dump_post("https://www.freejobalert.com/articles/upsc-cms-2026-3040941", "fja_post.html")
dump_post("https://www.sarkariexam.com/up-police-si-2025/", "se_post.html")
print("Dumped FJA and SE posts.")
