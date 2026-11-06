"""
main.py - Front-end del compilador (lexico + sintactico + semantico).

Uso:
    python main.py entrada.pse [nombre_base]

Genera siempre tres archivos JSON junto a la entrada (o con el nombre_base dado):
    <base>.lex  lista de tokens (y errores lexicos)
    <base>.syn  arbol sintactico abstracto, AST (y errores sintacticos)
    <base>.sem  AST anotado + tabla de simbolos (y errores semanticos)

Si una fase falla, las siguientes no se ejecutan (evita errores en cascada) y su
archivo indica "omitido" y la fase que lo causo. Codigo de salida: 0 ok, 1 error.
"""
import json
import sys
from pathlib import Path

from lexer import AnalizadorLexico
from parser import parsear_tokens
from semantic import analizar_semantica

EXTENSIONES_VALIDAS = {".pse", ".txt"}


def _escribir_json(ruta: str, datos: dict) -> None:
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)


def _omitido(fase_causa: str) -> dict:
    return {"exito": False, "omitido": True,
            "motivo": f"No se ejecutó: la fase {fase_causa} terminó con errores"}


def _reportar(errores) -> None:
    for e in errores:
        col = f", columna {e.columna}" if e.columna is not None else ""
        print(f"  [{e.fase}] línea {e.linea}{col}: {e.mensaje}")


def compilar(ruta_entrada: str, base: str) -> int:
    ruta_lex, ruta_syn, ruta_sem = f"{base}.lex", f"{base}.syn", f"{base}.sem"

    try:
        codigo = Path(ruta_entrada).read_text(encoding="utf-8")
    except OSError as e:
        print(f"No se pudo leer '{ruta_entrada}': {e}")
        return 1

    # ---------------- 1. Lexico ----------------
    lexer = AnalizadorLexico(codigo)
    lexer.analizar()
    lexer.exportar_json(ruta_lex)
    if lexer.errores:
        print(f"[FALLO] Léxico: {len(lexer.errores)} error(es)")
        _reportar(lexer.errores)
        _escribir_json(ruta_syn, _omitido("léxica"))
        _escribir_json(ruta_sem, _omitido("léxica"))
        return 1
    print(f"[OK] Léxico: {len(lexer.tokens)} tokens -> {ruta_lex}")

    # ---------------- 2. Sintactico ----------------
    ast, errores_sin = parsear_tokens(lexer.tokens)
    if errores_sin:
        print(f"[FALLO] Sintáctico: {len(errores_sin)} error(es)")
        _reportar(errores_sin)
        _escribir_json(ruta_syn, {"exito": False, "errores": [e.to_dict() for e in errores_sin]})
        _escribir_json(ruta_sem, _omitido("sintáctica"))
        return 1
    # el .syn se escribe ANTES del semantico para que no incluya las anotaciones
    _escribir_json(ruta_syn, {"exito": True, "ast": ast.to_dict()})
    print(f"[OK] Sintáctico: AST -> {ruta_syn}")

    # ---------------- 3. Semantico ----------------
    errores_sem, tabla = analizar_semantica(ast)
    _escribir_json(ruta_sem, {
        "exito": not errores_sem,
        "errores": [e.to_dict() for e in errores_sem],
        "tabla_simbolos": tabla,
        "ast_anotado": ast.to_dict(),
    })
    if errores_sem:
        print(f"[FALLO] Semántico: {len(errores_sem)} error(es)")
        _reportar(errores_sem)
        return 1
    print(f"[OK] Semántico: AST anotado y tabla de símbolos -> {ruta_sem}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python main.py <entrada.pse|.txt> [nombre_base]")
        sys.exit(1)

    entrada = Path(sys.argv[1])
    if entrada.suffix.lower() not in EXTENSIONES_VALIDAS:
        print(f"Aviso: se esperaba una entrada .pse o .txt, se recibió '{entrada.suffix}'")
    base = sys.argv[2] if len(sys.argv) > 2 else str(entrada.with_suffix(""))
    sys.exit(compilar(str(entrada), base))
