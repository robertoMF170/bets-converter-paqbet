import importlib
import subprocess
import sys
import threading
import time
import webbrowser

REQUIRED = {
    "flask": "flask",
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "pyngrok": "pyngrok",
}

PORT = 8000


def ensure_deps():
    missing = []
    for module, pip_name in REQUIRED.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(pip_name)

    if missing:
        print(f"[SETUP] A instalar dependências em falta: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        print("[SETUP] Dependências instaladas.")


def open_browser_later(url, delay=2.0):
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()


def start_ngrok():
    import os
    from pyngrok import ngrok, exception as ngrok_exception

    token = os.environ.get("NGROK_AUTHTOKEN", "")
    token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ngrok_token.txt")
    if not token and os.path.exists(token_file):
        with open(token_file) as f:
            token = f.read().strip()
    if token:
        try:
            ngrok.set_auth_token(token)
            print("[NGROK] Token configurado.")
        except Exception as e:
            print(f"[AVISO] Falha ao configurar o token: {e}")

    try:
        domain = os.environ.get("NGROK_DOMAIN", "")
        domain_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ngrok_domain.txt")
        if not domain and os.path.exists(domain_file):
            with open(domain_file) as f:
                domain = f.read().strip()

        if domain:
            print(f"[NGROK] A usar domínio fixo: {domain}")
            public = ngrok.connect(PORT, "http", domain=domain)
        else:
            public = ngrok.connect(PORT, "http")
        return public.public_url
    except ngrok_exception.PyngrokNgrokError as e:
        print(f"[AVISO] ngrok falhou: {e}")
        print("Se for erro de autenticação (ERR_NGROK_4018):")
        print("  1. Cria conta grátis em https://dashboard.ngrok.com/signup")
        print("  2. Copia o token de https://dashboard.ngrok.com/get-started/your-authtoken")
        print("  3. Ou cria o ficheiro ngrok_token.txt aqui na pasta com o token dentro")
        print("     ou corre: ngrok.exe config add-authtoken O_TEU_TOKEN")
        print("Para domínio FIXO (mesmo link sempre):")
        print("  - Cloud Side -> Domains -> cria o domínio grátis (ex: robs.ngrok-free.app)")
        print("  - Cria o ficheiro ngrok_domain.txt aqui na pasta com o domínio dentro")
        return None


def main():
    ensure_deps()

    print("=" * 60)
    print("  SrRobs - Bets Converter  |  a arrancar o servidor...")
    print("=" * 60)

    public_url = start_ngrok()
    local_url = f"http://127.0.0.1:{PORT}"

    print()
    print(f"  [LOCAL] {local_url}")
    if public_url:
        print(f"  [NGROK] {public_url}  <- partilha este link")
    else:
        print("  [NGROK] túnel indisponível (a continuar só em local)")
    print("=" * 60)
    print("  Debugs aparecem abaixo. Ctrl+C para parar.")
    print("=" * 60)
    print()

    open_browser_later(public_url or local_url)

    import app as flask_app
    try:
        flask_app.app.run(host="0.0.0.0", port=PORT, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n[STOP] A encerrar...")
    finally:
        try:
            from pyngrok import ngrok
            ngrok.kill()
        except Exception:
            pass


if __name__ == "__main__":
    main()
