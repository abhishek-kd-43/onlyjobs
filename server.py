import http.server
import socketserver
import json
import os
import subprocess
import urllib.parse

PORT = 8000
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')
SCRAPE_STATUS_FILE = os.path.join(os.path.dirname(__file__), 'scrape_status.json')
DATA_CATEGORIES = ('results', 'admit_cards', 'latest_jobs', 'answer_keys')


def normalize_data_payload(payload):
    """Accept both legacy and current payload shapes and return a safe dict."""
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a JSON object')

    normalized = {'status': payload.get('status', 'success')}
    has_any_category = False

    for category in DATA_CATEGORIES:
        value = payload.get(category, [])
        if value is None:
            value = []
        if not isinstance(value, list):
            raise ValueError(f'Invalid data format for {category}')
        normalized[category] = value
        has_any_category = has_any_category or bool(value) or category in payload

    if not has_any_category:
        raise ValueError('Invalid data format')

    return normalized

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/scraped-data':
            try:
                if not os.path.exists(DATA_FILE):
                    self.send_response(404)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'data.json not found'}).encode('utf-8'))
                    return
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = normalize_data_payload(json.load(f))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
        elif self.path == '/api/scrape-status':
            try:
                if not os.path.exists(SCRAPE_STATUS_FILE):
                    payload = {
                        'status': 'idle',
                        'started_at': None,
                        'finished_at': None,
                        'duration_seconds': None,
                        'counts': {},
                        'sources': ['sarkariresult', 'freejobalert', 'sarkariexam'],
                        'error': None
                    }
                else:
                    with open(SCRAPE_STATUS_FILE, 'r', encoding='utf-8') as f:
                        payload = json.load(f)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
        else:
            return super().do_GET()

    def do_POST(self):
        if self.path == '/api/scraped-data':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                new_data = normalize_data_payload(json.loads(post_data.decode('utf-8')))
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, indent=2, ensure_ascii=False)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'message': 'Data updated'}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        elif self.path == '/api/scrape':
            try:
                # Trigger scraper securely in background
                subprocess.Popen(['python3', 'scraper.py'])
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'message': 'Scraper started successfully. It may take 30s.'}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

class MyTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    with MyTCPServer(("", PORT), CustomHandler) as httpd:
        print(f"Custom Serving at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
