#!/usr/bin/env python3
"""
servidor.py — Servidor local del dashboard de confort térmico (solo biblioteca estándar).

Sirve el dashboard y lee, en cada carga de la página, TODOS los .csv de la carpeta
datos/ del repositorio. Para agregar resultados basta con copiar más CSV a datos/
y recargar el navegador.

Uso:  python dashboard/servidor.py [--puerto 8000] [--datos ruta/a/datos]
Rutas:
  /              dashboard (dashboard/index.html y archivos vecinos)
  /api/csv       lista JSON de los .csv en datos/
  /datos/<a>.csv contenido de un CSV de datos/
"""
import argparse, json, os, webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD = os.path.join(RAIZ, "dashboard")


def crear_handler(carpeta_datos):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=DASHBOARD, **kw)

        def do_GET(self):
            ruta = unquote(urlparse(self.path).path)
            if ruta == "/api/csv":
                return self.lista_csv()
            if ruta.startswith("/datos/"):
                return self.archivo_csv(ruta[len("/datos/"):])
            if ruta.endswith(".py"):
                return self.send_error(404)
            return super().do_GET()

        def lista_csv(self):
            archivos = sorted(f for f in os.listdir(carpeta_datos) if f.lower().endswith(".csv"))
            cuerpo = json.dumps(archivos).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def archivo_csv(self, nombre):
            # solo archivos .csv directamente dentro de datos/ (sin subcarpetas ni "..")
            if os.path.basename(nombre) != nombre or not nombre.lower().endswith(".csv"):
                return self.send_error(404)
            ruta = os.path.join(carpeta_datos, nombre)
            if not os.path.isfile(ruta):
                return self.send_error(404)
            with open(ruta, "rb") as f:
                cuerpo = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=8000)
    ap.add_argument("--datos", default=os.path.join(RAIZ, "datos"))
    ap.add_argument("--sin-navegador", action="store_true")
    a = ap.parse_args()
    datos = os.path.abspath(a.datos)
    if not os.path.isdir(datos):
        raise SystemExit(f"No existe la carpeta de datos: {datos}")
    # si el puerto está ocupado por otro programa, prueba los siguientes
    for puerto in range(a.puerto, a.puerto + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", puerto), crear_handler(datos))
            break
        except OSError:
            print(f"Puerto {puerto} ocupado, probando {puerto + 1}…")
    else:
        raise SystemExit(f"No hay puertos libres entre {a.puerto} y {a.puerto + 19}; usa --puerto")
    url = f"http://localhost:{puerto}/"
    print(f"Dashboard en {url}  (datos: {datos})  — Ctrl+C para salir")
    if not a.sin_navegador:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
