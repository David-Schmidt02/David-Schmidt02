"""Mide hábitos y lenguajes a partir de los clones locales y guarda solo totales en kpis/datos.json.

Corre en la máquina propia: lee `git log` de los repos que encuentre bajo las carpetas indicadas y
cuenta los commits del autor. No guarda nombres de repos, archivos, mensajes ni código.

Uso: python3 kpis/medir.py ~/Proyectos ~/Trabajo --autor mail1@ejemplo.com --autor mail2@ejemplo.com
"""
import argparse
import json
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path

LENGUAJES = {
    ".py": "Python", ".go": "Go", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript",
    ".jsx": "JavaScript", ".mjs": "JavaScript", ".c": "C", ".h": "C", ".php": "PHP", ".sql": "SQL",
    ".sh": "Shell", ".java": "Java", ".rs": "Rust", ".kt": "Kotlin",
    ".html": "HTML/SCSS", ".scss": "HTML/SCSS", ".css": "HTML/SCSS",
}
IGNORAR = ("node_modules/", "/dist/", "/vendor/", ".min.", "migrations/")
CARPETAS_EXCLUIDAS = {"node_modules", ".venv", "dist"}


def repos_bajo(carpeta: Path) -> list[Path]:
    encontrados = []
    for git in carpeta.rglob(".git"):
        if not CARPETAS_EXCLUIDAS.intersection(git.parts):
            encontrados.append(git.parent)
    return encontrados


def commits_del_autor(repo: Path, autores: list[str]) -> str:
    filtros = [f"--author={a}" for a in autores]
    resultado = subprocess.run(
        ["git", "-C", str(repo), "log", "--all", "--no-merges", *filtros,
         "--date=format:%u %H", "--format=@@%H %ad", "--numstat"],
        capture_output=True, text=True, errors="replace",
    )
    return resultado.stdout


def medir(carpetas: list[Path], autores: list[str]) -> dict:
    vistos: set[str] = set()
    # Cada commit suma 1 a cada lenguaje que toca: mide en cuántos commits se usó, no cuánto código hay
    por_hora, por_dia, por_lenguaje = Counter(), Counter(), Counter()
    for repo in sorted({r for c in carpetas for r in repos_bajo(c)}):
        actual, tocados = None, set()
        for fila in commits_del_autor(repo, autores).splitlines() + ["@@fin 1 0"]:
            if fila.startswith("@@"):
                por_lenguaje.update(tocados)
                tocados = set()
                sha, dia, hora = fila[2:].split()
                actual = None if sha in vistos or sha == "fin" else sha
                if actual:
                    vistos.add(sha)
                    por_dia[int(dia)] += 1
                    por_hora[int(hora)] += 1
            elif actual and fila.strip():
                _agregadas, _quitadas, ruta = fila.split("\t", 2)
                lenguaje = LENGUAJES.get(Path(ruta).suffix.lower())
                if lenguaje and not any(x in ruta for x in IGNORAR):
                    tocados.add(lenguaje)
    total = sum(por_lenguaje.values()) or 1
    return {
        "generado": date.today().isoformat(),
        "commits": len(vistos),
        "por_hora": [por_hora[h] for h in range(24)],
        "por_dia_semana": [por_dia[d] for d in range(1, 8)],  # lunes a domingo
        "lenguajes": [
            {"nombre": nombre, "commits": n, "porcentaje": round(100 * n / total, 1)}
            for nombre, n in por_lenguaje.most_common(6)
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("carpetas", nargs="+", type=Path)
    parser.add_argument("--autor", action="append", required=True, help="Mail con el que firmás los commits")
    args = parser.parse_args()
    datos = medir([c.expanduser() for c in args.carpetas], args.autor)
    destino = Path(__file__).parent / "datos.json"
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(datos, ensure_ascii=False, indent=2))
