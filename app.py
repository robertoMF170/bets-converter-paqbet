import time

from flask import Flask, request, jsonify, send_file
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

PAQBET_URL = "https://paqbet.com/"
PAQBET_CONVERT_URL = "https://paqbet.com/convert/booking_codes"

MAX_ATTEMPTS = 3
RETRY_DELAY = 1
CACHE_TTL = 600

_results_cache = {}

PAQBET_ALIASES = {
    'betandyou': '1xbet:xx',
}

PRETTY_NAMES = {
    'betandyou': 'BetAndYou',
    '1xbet:xx': '1xbet',
    '22bet': '22bet',
    'bet9ja': 'Bet9ja',
    'megapari': 'Megapari',
    'sportybet:ng': 'Sportybet',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': PAQBET_URL,
}


@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response


def err_view(msg):
    return jsonify({"view": f"<span style='color:var(--red);'>{msg}</span>"})


def attempt_convert(bet_code, convert_from, convert_to):
    session = requests.Session()
    session.headers.update(HEADERS)

    res = session.get(PAQBET_URL, timeout=(4, 8))
    print(f"[DEBUG] GET {PAQBET_URL} -> {res.status_code} (cookies: {len(session.cookies)})")

    soup = BeautifulSoup(res.text, 'html.parser')
    csrf_input = soup.find('input', {'name': lambda x: x and x.startswith('csrf_new')})
    if not csrf_input:
        print(f"[DEBUG] CSRF não encontrado. Snippet: {res.text[:300]}")
        raise NoCsrfError()

    csrf_name = csrf_input['name']
    csrf_value = csrf_input['value']
    print(f"[DEBUG] CSRF obtido: {csrf_name} = {csrf_value[:16]}...")

    payload = {
        'code': bet_code,
        'convert_from': convert_from,
        'convert_to': convert_to,
        csrf_name: csrf_value,
        'X-Requested-With': 'XMLHttpRequest',
    }

    post_res = session.post(PAQBET_CONVERT_URL, data=payload, timeout=(5, 10))
    print(f"[DEBUG] POST {PAQBET_CONVERT_URL} -> {post_res.status_code}")

    try:
        json_resp = post_res.json()
        print(f"[DEBUG] Resposta JSON ok: {str(json_resp)[:300]}")
        return json_resp
    except ValueError:
        print(f"[DEBUG] Resposta NÃO é JSON: {post_res.text[:300]}")
        raise BadResponseError(post_res.status_code)


class NoCsrfError(Exception):
    pass


class BadResponseError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


@app.route('/')
def index():
    return send_file('index.html')


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


@app.route('/api/convert', methods=['POST', 'OPTIONS'])
def convert():
    if request.method == 'OPTIONS':
        return ('', 204)

    data = request.form
    bet_code = data.get('code')
    convert_from = data.get('convert_from')
    convert_to = data.get('convert_to')

    print(f"\n[DEBUG] Pedido recebido: code={bet_code!r} from={convert_from!r} to={convert_to!r}")

    if not bet_code or not convert_from or not convert_to:
        return err_view("Erro: Preenche todos os campos.")

    real_from = PAQBET_ALIASES.get(convert_from, convert_from)
    real_to = PAQBET_ALIASES.get(convert_to, convert_to)

    if real_from == real_to:
        label_from = PRETTY_NAMES.get(convert_from, convert_from)
        label_to = PRETTY_NAMES.get(convert_to, convert_to)
        print(f"[DEBUG] Mesma plataforma ({label_from} <-> {label_to}): a devolver o código tal como está")
        view = (
            f"<a onclick=\"copy_text('{bet_code}')\">"
            f"<span>{label_from} &gt;&gt; {label_to}</span>"
            f"<h6>{bet_code}</h6>"
            f"<span>Mesma plataforma: o código nao muda. Toca para copiar.</span>"
            f"</a>"
        )
        return jsonify({"view": view})

    cache_key = (bet_code.strip().upper(), real_from, real_to)
    cached = _results_cache.get(cache_key)
    if cached and time.time() - cached[0] < CACHE_TTL:
        print(f"[DEBUG] A devolver resultado em cache ({time.time() - cached[0]:.0f}s depois)")
        return jsonify(cached[1])

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            json_resp = attempt_convert(bet_code, real_from, real_to)
            _results_cache[cache_key] = (time.time(), json_resp)
            return jsonify(json_resp)
        except NoCsrfError:
            return err_view("Erro: Não foi possível obter o token CSRF do servidor.")
        except BadResponseError as e:
            print(f"[DEBUG] Resposta inválida na tentativa {attempt}/{MAX_ATTEMPTS}")
            if attempt == MAX_ATTEMPTS:
                return err_view(f"Erro: resposta inesperada do PaQbet (HTTP {e.status_code}).")
        except (requests.Timeout, requests.ConnectionError) as e:
            print(f"[DEBUG] {type(e).__name__} na tentativa {attempt}/{MAX_ATTEMPTS}")
            if attempt == MAX_ATTEMPTS:
                return err_view("Erro: o PaQbet não respondeu após várias tentativas. Tenta de novo.")
        except Exception as e:
            print(f"[DEBUG] Exceção no backend: {type(e).__name__}: {e}")
            return err_view(f"Erro no backend local: {e}")

        if attempt < MAX_ATTEMPTS:
            print(f"[DEBUG] A tentar novamente em {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    return err_view("Erro: o PaQbet não respondeu.")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True, use_reloader=False)
