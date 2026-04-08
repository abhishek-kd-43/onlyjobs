import requests
from bs4 import BeautifulSoup

try:
    with open('debug_sarkari.html', 'r', encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    
    columns = soup.find_all('div', id='post')
    for i, col in enumerate(columns):
        first_text = col.text.strip().split('\n')[0] if col.text.strip() else 'Empty'
        first_a = col.find('a')
        first_a_text = first_a.text.strip() if first_a else 'No link'
        print(f"Column {i}: Header starts with -> {first_text[:30]}, First link -> {first_a_text}")
         
except Exception as e:
    print(f"Error: {e}")
