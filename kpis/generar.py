"""Dibuja las tarjetas del perfil en pixel art (SVG) a partir de datos públicos y de kpis/datos.json.

Sin tokens: el calendario de contribuciones se lee de la página pública del perfil (ya incluye las
contribuciones privadas como cantidades) y los hábitos y lenguajes salen de kpis/medir.py.
Uso: python3 kpis/generar.py <usuario> <carpeta_de_salida>
"""
import base64
import io
import json
import random
import re
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

DIR = Path(__file__).parent
FUENTE = base64.b64encode((DIR / "pixelify-sans.woff2").read_bytes()).decode()
FUENTE_NUMEROS = base64.b64encode((DIR / "vt323.woff2").read_bytes()).decode()

OSCURO = {"fondo": "#12111a", "panel": "#1c1a27", "tinta": "#eeecf6", "tinta2": "#a49fbd", "acento": "#9d88ff",
          "naranja": "#f0935a", "vacio": "#232032", "niveles": ["#232032", "#3b2f7a", "#5b3fd1", "#9d88ff", "#f0935a"]}
CLARO = {"fondo": "#ffffff", "panel": "#f3f1fb", "tinta": "#1f1d2b", "tinta2": "#5d5a70", "acento": "#5b3fd1",
         "naranja": "#e0702c", "vacio": "#ebe8f5", "niveles": ["#ebe8f5", "#d9d0ff", "#a993ff", "#6a52d6", "#e0702c"]}
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
DIAS_LARGOS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos"]


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def estilo(p: dict) -> str:
    return f"""<style>
@font-face {{ font-family: 'Pixelify Sans'; src: url(data:font/woff2;base64,{FUENTE}) format('woff2'); }}
@font-face {{ font-family: 'VT323'; src: url(data:font/woff2;base64,{FUENTE_NUMEROS}) format('woff2'); }}
text {{ font-family: 'VT323', ui-monospace, monospace; font-size: 17px; fill: {p['tinta']}; }}
.chico {{ font-size: 15px; fill: {p['tinta2']}; }}
.pixel {{ font-family: 'Pixelify Sans', ui-monospace, monospace; }}
.titulo {{ font-family: 'Pixelify Sans', ui-monospace, monospace; font-size: 16px; fill: {p['acento']}; }}
</style>"""


def svg(ancho: int, alto: int, p: dict, cuerpo: str, titulo: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" viewBox="0 0 {ancho} {alto}" '
            f'shape-rendering="crispEdges" role="img" aria-label="{titulo}"><title>{titulo}</title>{estilo(p)}'
            f'<rect width="{ancho}" height="{alto}" fill="{p["fondo"]}"/>{cuerpo}</svg>')


def marco(ancho: int, alto: int, p: dict) -> str:
    """Borde de 2 px con las esquinas recortadas, como una ventana de videojuego."""
    c, g = p["acento"], 2
    return (f'<rect x="{g*2}" y="0" width="{ancho-g*4}" height="{g}" fill="{c}"/>'
            f'<rect x="{g*2}" y="{alto-g}" width="{ancho-g*4}" height="{g}" fill="{c}"/>'
            f'<rect x="0" y="{g*2}" width="{g}" height="{alto-g*4}" fill="{c}"/>'
            f'<rect x="{ancho-g}" y="{g*2}" width="{g}" height="{alto-g*4}" fill="{c}"/>'
            f'<rect x="{g}" y="{g}" width="{g}" height="{g}" fill="{c}"/><rect x="{ancho-g*2}" y="{g}" width="{g}" height="{g}" fill="{c}"/>'
            f'<rect x="{g}" y="{alto-g*2}" width="{g}" height="{g}" fill="{c}"/><rect x="{ancho-g*2}" y="{alto-g*2}" width="{g}" height="{g}" fill="{c}"/>')


# ---------- Datos ----------

def calendario(usuario: str) -> list[tuple[date, int, int]]:
    """(fecha, contribuciones, nivel 0-4) de la página pública del perfil, sin token."""
    pedido = urllib.request.Request(f"https://github.com/users/{usuario}/contributions", headers={"User-Agent": "kpis"})
    html = urllib.request.urlopen(pedido, timeout=30).read().decode()
    celdas = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})" id="([^"]+)"[^>]*data-level="(\d)"', html)
    cantidades = {}
    for celda_id, texto in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]+)</tool-tip>', html):
        numero = re.match(r"([\d,]+) contribution", texto)
        cantidades[celda_id] = int(numero.group(1).replace(",", "")) if numero else 0
    return sorted((date.fromisoformat(f), cantidades.get(i, 0), int(n)) for f, i, n in celdas)


def rachas(dias: list[tuple[date, int, int]]) -> tuple[int, int]:
    mas_larga = actual = 0
    for _, cantidad, _ in dias:
        actual = actual + 1 if cantidad else 0
        mas_larga = max(mas_larga, actual)
    # La racha actual no se corta si hoy todavía no hubo contribuciones
    vigente = 0
    for i, (_, cantidad, _) in enumerate(reversed(dias)):
        if cantidad:
            vigente += 1
        elif i:
            break
    return vigente, mas_larga


def avatar(usuario: str, lado: int = 24) -> str:
    """Avatar público reducido a una grilla de píxeles, embebido como PNG."""
    pedido = urllib.request.Request(f"https://github.com/{usuario}.png?size=96", headers={"User-Agent": "kpis"})
    imagen = Image.open(io.BytesIO(urllib.request.urlopen(pedido, timeout=30).read())).convert("RGB")
    imagen = imagen.resize((lado, lado), Image.Resampling.BOX).quantize(colors=24).convert("RGB")
    imagen = imagen.resize((lado * 4, lado * 4), Image.Resampling.NEAREST)
    salida = io.BytesIO()
    imagen.save(salida, "PNG")
    return base64.b64encode(salida.getvalue()).decode()


# ---------- Tarjetas ----------

def tarjeta_perfil(usuario: str, dias, datos: dict, p: dict) -> str:
    ancho, alto = 830, 190
    vigente, mas_larga = rachas(dias)
    total = sum(c for _, c, _ in dias)
    dia_fuerte = DIAS_LARGOS[max(range(7), key=lambda i: datos["por_dia_semana"][i])]
    hora_fuerte = max(range(24), key=lambda h: datos["por_hora"][h])
    filas = [
        ("Commits medidos", miles(datos["commits"])),
        ("Contribuciones del último año", miles(total)),
        ("Racha actual · más larga", f"{vigente} · {mas_larga} días"),
        ("Más activo", f"{dia_fuerte}, {hora_fuerte}:00 a {hora_fuerte + 1}:00"),
    ]
    cuerpo = [marco(ancho, alto, p)]
    # Cielo con estrellas fijas en píxeles
    for i in range(40):
        x, y = (i * 97 + 31) % (ancho - 20) + 10, (i * 53 + 17) % 70 + 10
        cuerpo.append(f'<rect x="{x}" y="{y}" width="2" height="2" fill="{p["acento"] if i % 3 else p["naranja"]}" opacity="0.5"/>')
    cuerpo.append(f'<image x="28" y="35" width="120" height="120" href="data:image/png;base64,{avatar(usuario)}" style="image-rendering:pixelated"/>')
    cuerpo.append(f'<rect x="26" y="33" width="124" height="124" fill="none" stroke="{p["acento"]}" stroke-width="2"/>')
    cuerpo.append(f'<text x="176" y="62" class="pixel" style="font-size:30px">David Schmidt</text>')
    cuerpo.append(f'<text x="176" y="86" class="titulo">Desarrollador de Software</text>')
    for i, (rotulo, valor) in enumerate(filas):
        y = 120 + i * 18
        cuerpo.append(f'<text x="176" y="{y}" class="chico">{rotulo}</text>')
        cuerpo.append(f'<text x="470" y="{y}" style="font-size:19px;fill:{p["naranja"] if i == 0 else p["tinta"]}">{valor}</text>')
    # Mini calendario de las últimas 12 semanas a la derecha
    ultimas = dias[-84:]
    for i, (_, _, nivel) in enumerate(ultimas):
        x, y = 640 + (i // 7) * 13, 40 + (i % 7) * 13
        cuerpo.append(f'<rect x="{x}" y="{y}" width="10" height="10" fill="{p["niveles"][nivel]}"/>')
    cuerpo.append(f'<text x="640" y="150" class="chico">últimas 12 semanas</text>')
    return svg(ancho, alto, p, "".join(cuerpo), f"David Schmidt: {datos['commits']} commits medidos, {total} contribuciones en el último año")


def barras(valores: list[int], x0: int, y0: int, alto: int, paso: int, ancho_barra: int, p: dict, destacar: int) -> str:
    """Barras hechas de bloques de 4 px, la más alta en naranja."""
    tope = max(valores) or 1
    piezas = []
    for i, v in enumerate(valores):
        bloques = round(v / tope * alto / 5)
        color = p["naranja"] if i == destacar else p["acento"]
        for b in range(bloques):
            piezas.append(f'<rect x="{x0 + i * paso}" y="{y0 - (b + 1) * 5}" width="{ancho_barra}" height="4" fill="{color}"/>')
        if not bloques:
            piezas.append(f'<rect x="{x0 + i * paso}" y="{y0 - 2}" width="{ancho_barra}" height="2" fill="{p["vacio"]}"/>')
    return "".join(piezas)


def tarjeta_habitos(datos: dict, p: dict) -> str:
    ancho, alto = 410, 230
    horas, dias = datos["por_hora"], datos["por_dia_semana"]
    hora_fuerte = max(range(24), key=lambda h: horas[h])
    dia_fuerte = max(range(7), key=lambda d: dias[d])
    cuerpo = [marco(ancho, alto, p), f'<text x="20" y="32" class="titulo">Hábitos</text>',
              f'<text x="{ancho - 20}" y="32" class="chico" text-anchor="end">{miles(datos["commits"])} commits</text>',
              f'<text x="20" y="56" class="chico">Commits por hora del día</text>',
              barras(horas, 20, 130, 60, 15, 11, p, hora_fuerte)]
    for h in (0, 6, 12, 18, 23):
        cuerpo.append(f'<text x="{20 + h * 15 + 5}" y="145" class="chico" text-anchor="middle">{h}</text>')
    cuerpo.append(f'<text x="20" y="170" class="chico">Por día de la semana</text>')
    cuerpo.append(barras(dias, 20, 205, 25, 52, 40, p, dia_fuerte).replace('height="4"', 'height="4"'))
    for d, nombre in enumerate(DIAS):
        cuerpo.append(f'<text x="{20 + d * 52 + 20}" y="220" class="chico" text-anchor="middle">{nombre}</text>')
    return svg(ancho, alto, p, "".join(cuerpo), "Hábitos de programación: commits por hora y por día de la semana")


def tarjeta_lenguajes(datos: dict, p: dict) -> str:
    ancho, alto = 410, 230
    cuerpo = [marco(ancho, alto, p), f'<text x="20" y="32" class="titulo">Lenguajes</text>',
              f'<text x="{ancho - 20}" y="32" class="chico" text-anchor="end">por líneas escritas</text>']
    for i, lenguaje in enumerate(datos["lenguajes"]):
        y = 64 + i * 27
        bloques = max(1, round(lenguaje["porcentaje"] / 100 * 30))
        color = p["naranja"] if i == 0 else p["acento"]
        cuerpo.append(f'<text x="20" y="{y + 10}" style="font-size:19px">{lenguaje["nombre"]}</text>')
        for b in range(30):
            cuerpo.append(f'<rect x="{120 + b * 7}" y="{y}" width="5" height="10" fill="{color if b < bloques else p["vacio"]}"/>')
        cuerpo.append(f'<text x="{ancho - 20}" y="{y + 9}" class="chico" text-anchor="end">{str(lenguaje["porcentaje"]).replace(".", ",")} %</text>')
    return svg(ancho, alto, p, "".join(cuerpo), "Lenguajes más usados, por líneas escritas")


def recorrido(posiciones: list[tuple[int, int, int]], azar: random.Random) -> list[tuple[int, int]]:
    """Camino celda por celda hacia días con contribuciones, con desvíos y vueltas al azar."""
    columnas = max(c for c, _, _ in posiciones) + 1
    pendientes = {(c, f) for c, f, nivel in posiciones if nivel}
    actual = (0, azar.randrange(7))
    camino = [actual]

    def mover(hacia):
        nonlocal actual
        actual = hacia
        camino.append(actual)
        pendientes.discard(actual)

    while pendientes:
        distancia = lambda d: abs(d[0] - actual[0]) + abs(d[1] - actual[1])
        minima = min(map(distancia, pendientes))
        cercanos = sorted(d for d in pendientes if distancia(d) <= minima + 3)
        destino = azar.choice(cercanos)
        while actual != destino:
            if azar.random() < 0.18:  # un desvío al azar, sin salirse del calendario
                c, f = actual
                vecinos = [(c + dc, f + df) for dc, df in ((1, 0), (-1, 0), (0, 1), (0, -1))
                           if 0 <= c + dc < columnas and 0 <= f + df < 7]
                for _ in range(azar.randint(1, 3)):
                    mover(azar.choice(vecinos))
                    c, f = actual
                    vecinos = [(c + dc, f + df) for dc, df in ((1, 0), (-1, 0), (0, 1), (0, -1))
                               if 0 <= c + dc < columnas and 0 <= f + df < 7]
                continue
            pasos = []
            if actual[0] != destino[0]:
                pasos.append((actual[0] + (1 if destino[0] > actual[0] else -1), actual[1]))
            if actual[1] != destino[1]:
                pasos.append((actual[0], actual[1] + (1 if destino[1] > actual[1] else -1)))
            mover(azar.choice(pasos))
    return camino


def ritmo(pasos: int, azar: random.Random) -> list[float]:
    """Segundo en que la cabeza llega a cada celda: anda a paso tranquilo, a veces acelera y a veces se frena."""
    tiempos, t, modo, restantes = [0.0], 0.0, "normal", 0
    for _ in range(pasos - 1):
        if restantes == 0:
            modo = azar.choices(["normal", "rapido", "lento"], weights=[6, 2, 2])[0]
            restantes = azar.randint(4, 14)
        restantes -= 1
        t += {"normal": 0.45, "rapido": 0.3, "lento": 0.7}[modo] * azar.uniform(0.85, 1.15)
        if azar.random() < 0.03:
            t += azar.uniform(0.6, 1.4)  # se queda quieta un momento
        tiempos.append(t)
    return tiempos


def vibora(dias, p: dict) -> str:
    """Una víbora que deambula por el calendario, se come los días con contribuciones y crece al comer.

    El azar depende de la fecha: el recorrido y el ritmo cambian todos los días.
    """
    celda, hueco, x0, y0 = 11, 3, 14, 14
    paso = celda + hueco
    inicio = dias[0][0] - timedelta(days=(dias[0][0].weekday() + 1) % 7)  # el calendario arranca en domingo
    posiciones = [((f - inicio).days // 7, (f - inicio).days % 7, nivel) for f, _, nivel in dias]
    niveles = {(c, f): nivel for c, f, nivel in posiciones}
    columnas = max(c for c, _, _ in posiciones) + 1
    ancho, alto = x0 * 2 + columnas * paso - hueco, y0 * 2 + 7 * paso - hueco
    azar = random.Random(dias[-1][0].isoformat())
    camino = recorrido(posiciones, azar)
    tiempos = ritmo(len(camino), azar)
    recorrida = tiempos[-1]
    duracion = recorrida + 4  # una pausa al final, con el calendario vacío, antes de volver a empezar
    centro = lambda c, f: (x0 + c * paso + celda / 2, y0 + f * paso + celda / 2)
    trazo = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in (centro(c, f) for c, f in camino))
    tramos = len(camino) - 1
    momentos_clave = ";".join(f"{t / duracion:.5f}" for t in tiempos) + ";1"

    comido_en = {}
    for i, posicion in enumerate(camino):
        if niveles.get(posicion) and posicion not in comido_en:
            comido_en[posicion] = tiempos[i]
    reglas, figuras = [], []
    for (c, f), nivel in niveles.items():
        x, y = x0 + c * paso, y0 + f * paso
        if nivel:
            momento = comido_en[(c, f)] / duracion * 100
            reglas.append(f"@keyframes c{c}_{f}{{0%,{momento:.2f}%{{fill:{p['niveles'][nivel]}}}{momento + 0.01:.2f}%,99.8%{{fill:{p['vacio']}}}}}"
                          f".c{c}_{f}{{animation:c{c}_{f} {duracion:.1f}s linear infinite}}")
            figuras.append(f'<rect class="c{c}_{f}" x="{x}" y="{y}" width="{celda}" height="{celda}" rx="2" fill="{p["niveles"][nivel]}"/>')
        else:
            figuras.append(f'<rect x="{x}" y="{y}" width="{celda}" height="{celda}" rx="2" fill="{p["vacio"]}"/>')

    # Arranca con 4 segmentos y suma uno cada 20 días comidos, hasta 14
    momentos = sorted(comido_en.values())
    largo_inicial, largo_maximo, cada = 4, 14, 20
    for k in range(largo_maximo):
        tam = celda - min(k, 6) * 0.6
        # Cada segmento va siempre k casilleros detrás de la cabeza, ande rápido o lento
        puntos = ";".join(f"{max(0, i - k) / tramos:.5f}" for i in range(len(camino))) + f";{max(0, tramos - k) / tramos:.5f}"
        color = p["naranja"] if k == 0 else p["acento"]
        opacidad = 1 - min(k, 10) * 0.04
        clase = ""
        if k >= largo_inicial:
            indice = (k - largo_inicial + 1) * cada - 1
            if indice >= len(momentos):
                break
            aparece = momentos[indice] / duracion * 100
            reglas.append(f"@keyframes s{k}{{0%,{aparece:.2f}%{{opacity:0}}{aparece + 0.01:.2f}%,99.8%{{opacity:{opacidad:.2f}}}}}"
                          f".s{k}{{animation:s{k} {duracion:.1f}s linear infinite}}")
            clase = f' class="s{k}"'
        figuras.append(
            f'<rect{clase} x="{-tam / 2:.1f}" y="{-tam / 2:.1f}" width="{tam:.1f}" height="{tam:.1f}" rx="2" fill="{color}" '
            f'opacity="{0 if clase else opacidad:.2f}">'
            f'<animateMotion path="{trazo}" dur="{duracion:.1f}s" repeatCount="indefinite" '
            f'keyPoints="{puntos}" keyTimes="{momentos_clave}" calcMode="linear"/></rect>'
        )
    cuerpo = [f"<style>{''.join(reglas)}</style>", *figuras]
    return svg(ancho, alto, p, "".join(cuerpo), "Víbora que deambula por el calendario y se come los días con contribuciones del último año")


MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def tarjeta_anio(dias, p: dict) -> str:
    """Contribuciones de los últimos 12 meses, una barra por semana, con los meses abajo."""
    ancho, alto = 830, 200
    semanas: dict[date, int] = {}
    for fecha, cantidad, _ in dias:
        lunes = fecha - timedelta(days=fecha.weekday())
        semanas[lunes] = semanas.get(lunes, 0) + cantidad
    lunes_ordenados = sorted(semanas)[-52:]
    valores = [semanas[l] for l in lunes_ordenados]
    total = sum(c for _, c, _ in dias)
    mejor = max(range(len(valores)), key=lambda i: valores[i])
    x0, paso = 24, 15
    cuerpo = [marco(ancho, alto, p), f'<text x="20" y="32" class="titulo">Últimos 12 meses</text>',
              f'<text x="{ancho - 20}" y="32" class="chico" text-anchor="end">{miles(total)} contribuciones · '
              f'mejor semana: {valores[mejor]}</text>',
              barras(valores, x0, 160, 100, paso, 11, p, mejor)]
    mes_anterior = None
    for i, lunes in enumerate(lunes_ordenados):
        if lunes.month != mes_anterior:
            mes_anterior = lunes.month
            cuerpo.append(f'<text x="{x0 + i * paso}" y="182" class="chico">{MESES[lunes.month - 1]}</text>')
    return svg(ancho, alto, p, "".join(cuerpo), f"Contribuciones por semana en los últimos 12 meses: {total} en total")


if __name__ == "__main__":
    usuario, salida = sys.argv[1], Path(sys.argv[2])
    salida.mkdir(parents=True, exist_ok=True)
    datos = json.loads((DIR / "datos.json").read_text(encoding="utf-8"))
    dias = calendario(usuario)
    for sufijo, paleta in (("", CLARO), ("-oscura", OSCURO)):
        (salida / f"perfil{sufijo}.svg").write_text(tarjeta_perfil(usuario, dias, datos, paleta), encoding="utf-8")
        (salida / f"habitos{sufijo}.svg").write_text(tarjeta_habitos(datos, paleta), encoding="utf-8")
        (salida / f"lenguajes{sufijo}.svg").write_text(tarjeta_lenguajes(datos, paleta), encoding="utf-8")
        (salida / f"vibora{sufijo}.svg").write_text(vibora(dias, paleta), encoding="utf-8")
        (salida / f"anio{sufijo}.svg").write_text(tarjeta_anio(dias, paleta), encoding="utf-8")
    print(f"Tarjetas en {salida}: {len(dias)} días de calendario, {datos['commits']} commits medidos")
