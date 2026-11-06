"""
main.py - Compilador (lexico + sintactico + semantico + codigo intermedio y ejecucion).

Uso:
    python main.py entrada.pse [nombre_base] [--sin-ejecutar]

Genera siempre cinco archivos JSON junto a la entrada (o con el nombre_base dado):
    <base>.lex  lista de tokens (y errores lexicos)
    <base>.syn  arbol sintactico abstracto, AST (y errores sintacticos)
    <base>.sem  AST anotado + tabla de simbolos (y errores semanticos)
    <base>.tac  codigo de tres direcciones (TAC)
    <base>.opt  TAC optimizado
Si el lexico termina sin errores, tambien genera:
    <base>.der  arbol de derivacion (lo escribe exportar_syn junto con el .syn)

Si las cuatro primeras fases terminan sin errores, el programa se ejecuta con el TAC
optimizado (leer pide los valores por teclado). Con --sin-ejecutar solo se generan los archivos.

Si una fase falla, las siguientes no se ejecutan (evita errores en cascada) y su
archivo indica "omitido" y la fase que lo causo. Codigo de salida: 0 ok, 1 error.
"""
import json
import sys
from pathlib import Path

from lexer import AnalizadorLexico
from parser import parsear_tokens
from semantic import analizar_semantica
from exportar_syn import exportar_syn
from tac import GeneradorTAC, optimizar, ejecutar, exportar_tac

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


def _omitir(rutas, fase_causa: str) -> None:
    for ruta in rutas:
        _escribir_json(ruta, _omitido(fase_causa))


def compilar(ruta_entrada: str, base: str, ejecutar_programa: bool = True) -> int:
    ruta_lex, ruta_syn, ruta_sem = f"{base}.lex", f"{base}.syn", f"{base}.sem"
    ruta_tac, ruta_opt = f"{base}.tac", f"{base}.opt"

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
        _omitir((ruta_syn, ruta_sem, ruta_tac, ruta_opt), "léxica")
        return 1
    print(f"[OK] Léxico: {len(lexer.tokens)} tokens -> {ruta_lex}")

    # ---------------- 2. Sintactico ----------------
    ast, errores_sin = parsear_tokens(lexer.tokens)
    # exportar_syn escribe el .syn (AST y errores) y el .der (derivacion). Se llama ANTES del
    # semantico para que el .syn no incluya las anotaciones.
    exportar_syn(ast, errores_sin, ruta_syn)
    if errores_sin:
        print(f"[FALLO] Sintáctico: {len(errores_sin)} error(es)")
        _reportar(errores_sin)
        _omitir((ruta_sem, ruta_tac, ruta_opt), "sintáctica")
        return 1
    print(f"[OK] Sintáctico: AST -> {ruta_syn}, derivación -> {Path(ruta_syn).with_suffix('.der')}")

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
        _omitir((ruta_tac, ruta_opt), "semántica")
        return 1
    print(f"[OK] Semántico: AST anotado y tabla de símbolos -> {ruta_sem}")

    # ---------------- 4. Codigo intermedio (TAC) y optimizacion ----------------
    tac = GeneradorTAC().generar(ast)
    exportar_tac(tac, ruta_tac)
    print(f"[OK] TAC: {len(tac)} instrucciones -> {ruta_tac}")
    opt = optimizar(tac)
    exportar_tac(opt, ruta_opt, instrucciones_originales=len(tac))
    print(f"[OK] Optimización: {len(tac)} -> {len(opt)} instrucciones -> {ruta_opt}")

    # ---------------- 5. Ejecucion ----------------
    if not ejecutar_programa:
        return 0
    print("--- Ejecución ---")
    try:
        ejecutar(opt)
    except ZeroDivisionError:
        print("[FALLO] Ejecución: división entre cero")
        return 1
    except (IndexError, KeyError, TypeError, ValueError) as e:
        print(f"[FALLO] Ejecución: {type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    argumentos = [a for a in sys.argv[1:] if a != "--sin-ejecutar"]
    ejecutar_programa = len(argumentos) == len(sys.argv) - 1  # sin la bandera: se ejecuta
    if not argumentos:
        print("Uso: python main.py <entrada.pse|.txt> [nombre_base] [--sin-ejecutar]")
        sys.exit(1)

    entrada = Path(argumentos[0])
    if entrada.suffix.lower() not in EXTENSIONES_VALIDAS:
        print(f"Aviso: se esperaba una entrada .pse o .txt, se recibió '{entrada.suffix}'")
    base = argumentos[1] if len(argumentos) > 1 else str(entrada.with_suffix(""))
    sys.exit(compilar(str(entrada), base, ejecutar_programa))