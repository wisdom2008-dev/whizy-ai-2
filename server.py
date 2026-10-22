#!/usr/bin/env python3
"""WHIZY AI 2.0 hosted backend. Provider secrets remain server-side."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
import json, os, time, threading

HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', os.environ.get('WHIZY_PORT', '8787')))
ROOT = os.path.dirname(os.path.abspath(__file__))
MAX_BODY = 4 * 1024 * 1024
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
AI_BASE_URL = os.environ.get('AI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_MODEL = os.environ.get('AI_MODEL', 'gpt-4.1-mini')
IMAGE_MODEL = os.environ.get('IMAGE_MODEL', 'gpt-image-1')
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY', '')
RATE_LIMIT = int(os.environ.get('WHIZY_REQUESTS_PER_MINUTE', '20'))
_usage, _lock = {}, threading.Lock()

def read_json(handler):
    size = int(handler.headers.get('Content-Length', '0'))
    if size > MAX_BODY: raise ValueError('Request is too large (4 MB maximum).')
    return json.loads(handler.rfile.read(size) or b'{}')

def request_json(url, payload=None, headers=None, method='POST', timeout=120):
    h = {'Accept': 'application/json', 'User-Agent': 'WHIZY-AI-2.0'}
    if payload is not None: h['Content-Type'] = 'application/json'
    if headers: h.update(headers)
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, headers=h, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(12 * 1024 * 1024)
            try: return resp.status, json.loads(raw.decode('utf-8'))
            except Exception: return resp.status, {'error': {'message': 'Upstream returned invalid JSON.'}}
    except HTTPError as e:
        raw = e.read(4000).decode('utf-8', 'replace')
        try: result = json.loads(raw)
        except Exception: result = {'error': {'message': raw or str(e)}}
        return e.code, result
    except (URLError, TimeoutError, OSError) as e:
        return 502, {'error': {'message': f'Could not reach the AI service: {e}.'}}

def bearer(handler):
    value = handler.headers.get('Authorization', '')
    return value[7:].strip() if value.lower().startswith('bearer ') else ''

def identify_user(token):
    if not (SUPABASE_URL and SUPABASE_ANON_KEY and token): return None
    status, result = request_json(SUPABASE_URL + '/auth/v1/user', None,
        {'apikey': SUPABASE_ANON_KEY, 'Authorization': 'Bearer ' + token}, method='GET', timeout=15)
    if status != 200 or not isinstance(result, dict) or not result.get('id'): return None
    return str(result['id'])

def rate_allowed(user_id):
    now = time.time()
    with _lock:
        entries = [t for t in _usage.get(user_id, []) if now - t < 60]
        if len(entries) >= RATE_LIMIT:
            _usage[user_id] = entries
            return False
        entries.append(now); _usage[user_id] = entries
        return True

class Handler(SimpleHTTPRequestHandler):
    def end_json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store'); self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path == '/api/health':
            self.end_json(200, {'ok': True, 'name': 'WHIZY AI 2.0', 'authConfigured': bool(SUPABASE_URL and SUPABASE_ANON_KEY), 'aiConfigured': bool(AI_API_KEY)})
            return
        return super().do_GET()
    def do_POST(self):
        try:
            data = read_json(self)
            if self.path not in ('/api/chat', '/api/search', '/api/images'):
                return self.end_json(404, {'error': {'message': 'Unknown API route.'}})
            user_id = identify_user(bearer(self))
            if not user_id: return self.end_json(401, {'error': {'message': 'Sign in to use WHIZY AI.'}})
            if not rate_allowed(user_id): return self.end_json(429, {'error': {'message': 'Usage limit reached. Please wait a minute and try again.'}})
            if self.path == '/api/chat': self.chat(data)
            elif self.path == '/api/search': self.search(data)
            else: self.images(data)
        except ValueError as e: self.end_json(400, {'error': {'message': str(e)}})
        except Exception as e:
            print('[WHIZY ERROR]', repr(e)); self.end_json(500, {'error': {'message': 'The server could not complete that request.'}})
    def chat(self, d):
        if not AI_API_KEY: return self.end_json(503, {'error': {'message': 'AI service is not configured yet. The site owner must add AI_API_KEY in the server environment.'}})
        messages = d.get('messages')
        if not isinstance(messages, list) or not messages: return self.end_json(400, {'error': {'message': 'A non-empty messages array is required.'}})
        # Never accept provider URLs or secrets from the public browser.
        status, result = request_json(
    AI_BASE_URL + '/chat/completions',
    {
        'model': AI_MODEL,
        'messages': messages,
        'stream': False
    },
    {'Authorization': 'Bearer ' + AI_API_KEY},
    timeout=180
)

if status < 200 or status >= 300:
    print(f"[WHIZY AI ERROR] HTTP {status}: {json.dumps(result)[:1500]}")
    return self.end_json(status, result)
        content = (((result.get('choices') or [{}])[0]).get('message') or {}).get('content')
        if content is None: return self.end_json(502, {'error': {'message': 'AI provider returned no message content.'}})
        self.end_json(200, {'content': content, 'model': result.get('model', AI_MODEL), 'usage': result.get('usage')})
    def search(self, d):
        query = str(d.get('query') or '').strip()
        if not TAVILY_API_KEY: return self.end_json(503, {'error': {'message': 'Web research is not configured by the site owner yet.'}})
        if not query: return self.end_json(400, {'error': {'message': 'Enter a search query.'}})
        status, result = request_json('https://api.tavily.com/search', {'api_key': TAVILY_API_KEY, 'query': query, 'search_depth': 'advanced', 'max_results': 8, 'include_answer': True}, timeout=60)
        self.end_json(status, result)
    def images(self, d):
        if not AI_API_KEY: return self.end_json(503, {'error': {'message': 'Image generation is not configured by the site owner yet.'}})
        prompt = str(d.get('prompt') or '').strip()
        if not prompt: return self.end_json(400, {'error': {'message': 'Describe the image first.'}})
        size = d.get('size') if d.get('size') in ('1024x1024', '1536x1024', '1024x1536') else '1024x1024'
        payload = {'model': IMAGE_MODEL, 'prompt': prompt[:8000], 'size': size, 'n': 1}
        if d.get('quality') in ('standard', 'high'): payload['quality'] = 'high' if d.get('quality') == 'high' else 'medium'
        status, result = request_json(AI_BASE_URL + '/images/generations', payload, {'Authorization': 'Bearer ' + AI_API_KEY}, timeout=240)
        self.end_json(status, result)
    def log_message(self, fmt, *args): print('[WHIZY]', fmt % args)

if __name__ == '__main__':
    os.chdir(ROOT)
    print(f'WHIZY AI 2.0 hosted server on 0.0.0.0:{PORT}')
    print('Set Supabase auth + AI provider environment variables before public deployment.')
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
