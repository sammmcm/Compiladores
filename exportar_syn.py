"""
exportar_syn.py - Exportacion de la fase 2 (sintactico): .syn (AST + errores) y .der (arbol de derivacion).

No modifica parser.py: el arbol de derivacion se reconstruye a partir del AST siguiendo la BNF del reporte.
Los parentesis solo reaparecen cuando son necesarios por la precedencia; el lexema de un numero
se reconstruye desde su valor y el de una cadena se escribe con comillas dobles.

Uso independiente:
    python exportar_syn.py entrada.pse salida.syn      (tambien genera salida.der)

Codigos de salida: 0 sin errores, 1 si falta el archivo o los argumentos,
2 si hubo errores lexicos (no se parsea), 3 si hubo errores sintacticos.
"""
import json
import os
import sys

from lexer import AnalizadorLexico
from parser import (
    Programa, FuncionDecl, Asignacion, Si, Mientras, Para, Escribir, Leer, Retornar,
    LlamadaFuncion, OperacionBinaria, OperacionUnaria, Literal, Identificador,
    parsear_tokens,
)

# niveles de la cadena de expresiones, de menor a mayor precedencia
NIVELES = ["expresion", "comparacion", "suma", "termino", "unario", "llamada", "primario"]
PRIMARIO = 6


def _t(tipo, lexema):
    """Hoja del arbol: un token."""
    return {"token": tipo, "lexema": lexema}


def _r(regla, *hijos):
    """Nodo interno: una regla de la BNF con sus hijos."""
    return {"regla": regla, "hijos": list(hijos)}


def _kw(palabra):
    return _t("PALABRA_CLAVE", palabra)


# --------------------- expresiones ---------------------
def _nivel_natural(nodo) -> int:
    if isinstance(nodo, OperacionBinaria):
        if nodo.operador in ("+", "-"):
            return 2
        if nodo.operador in ("*", "/", "%"):
            return 3
        return 1
    if isinstance(nodo, OperacionUnaria):
        return 4
    if isinstance(nodo, LlamadaFuncion):
        return 5
    return PRIMARIO


def _terminal_literal(nodo: Literal):
    if nodo.tipo_valor == "booleano":
        return _kw("verdadero" if nodo.valor else "falso")
    if nodo.tipo_valor == "cadena":
        return _t("CADENA", f'"{nodo.valor}"')
    return _t("NUMERO", repr(nodo.valor) if nodo.tipo_valor == "decimal" else str(nodo.valor))


def _expr(nodo, nivel: int = 0):
    """Deriva `nodo` desde la regla NIVELES[nivel] hacia abajo."""
    regla = NIVELES[nivel]

    if nivel == PRIMARIO:
        if isinstance(nodo, Literal):
            return _r(regla, _terminal_literal(nodo))
        if isinstance(nodo, Identificador):
            return _r(regla, _t("IDENTIFICADOR", nodo.nombre))
        # expresion de menor precedencia: solo cabe entre parentesis
        return _r(regla, _t("PARENTESIS_IZQ", "("), _expr(nodo, 0), _t("PARENTESIS_DER", ")"))

    natural = _nivel_natural(nodo)
    if natural != nivel:
        return _r(regla, _expr(nodo, nivel + 1))  # la regla solo deja pasar al nivel siguiente

    if isinstance(nodo, OperacionBinaria):
        # asociatividad izquierda: se aplana la columna izquierda (a - b - c)
        operandos, operadores = [nodo.derecha], [nodo.operador]
        izq = nodo.izquierda
        while isinstance(izq, OperacionBinaria) and _nivel_natural(izq) == nivel:
            operandos.append(izq.derecha)
            operadores.append(izq.operador)
            izq = izq.izquierda
        hijos = [_expr(izq, nivel + 1)]
        for op, der in zip(reversed(operadores), reversed(operandos)):
            tipo_op = "OP_REL" if nivel == 1 else "OP_ARITMETICO"
            hijos += [_t(tipo_op, op), _expr(der, nivel + 1)]
        return _r(regla, *hijos)

    if isinstance(nodo, OperacionUnaria):
        return _r(regla, _t("OP_ARITMETICO", "-"), _expr(nodo.operando, 4))

    # LlamadaFuncion
    hijos = [_r("primario", _t("IDENTIFICADOR", nodo.nombre)), _t("PARENTESIS_IZQ", "(")]
    if nodo.argumentos:
        args = []
        for i, a in enumerate(nodo.argumentos):
            if i:
                args.append(_t("COMA", ","))
            args.append(_expr(a, 0))
        hijos.append(_r("argumentos", *args))
    hijos.append(_t("PARENTESIS_DER", ")"))
    return _r(regla, *hijos)


# --------------------- instrucciones ---------------------
def _asignacion(n: Asignacion):
    return _r("asignacion", _t("IDENTIFICADOR", n.identificador),
              _t("OP_ASIGNACION", "="), _expr(n.expresion))


def _bloque(instrucciones):
    return _r("bloque", _t("LLAVE_IZQ", "{"), *[_instruccion(i) for i in instrucciones],
              _t("LLAVE_DER", "}"))


def _instruccion(n):
    pc = _t("PUNTOCOMA", ";")
    pi, pd = _t("PARENTESIS_IZQ", "("), _t("PARENTESIS_DER", ")")
    if isinstance(n, Asignacion):
        return _r("instruccion", _asignacion(n), pc)
    if isinstance(n, LlamadaFuncion):
        return _r("instruccion", _expr(n, 5), pc)
    if isinstance(n, Si):
        hijos = [_kw("si"), pi, _expr(n.condicion), pd, _bloque(n.bloque_si)]
        if n.bloque_sino:
            hijos += [_kw("sino"), _bloque(n.bloque_sino)]
        return _r("instruccion", _r("si", *hijos))
    if isinstance(n, Mientras):
        return _r("instruccion", _r("mientras", _kw("mientras"), pi, _expr(n.condicion), pd,
                                    _bloque(n.cuerpo)))
    if isinstance(n, Para):
        return _r("instruccion", _r("para", _kw("para"), pi, _asignacion(n.inicializacion), pc,
                                    _expr(n.condicion), pc, _asignacion(n.incremento), pd,
                                    _bloque(n.cuerpo)))
    if isinstance(n, Escribir):
        return _r("instruccion", _r("escribir", _kw("escribir"), pi, _expr(n.expresion), pd, pc))
    if isinstance(n, Leer):
        return _r("instruccion", _r("leer", _kw("leer"), pi,
                                    _t("IDENTIFICADOR", n.identificador), pd, pc))
    if isinstance(n, Retornar):
        return _r("instruccion", _r("retornar", _kw("retornar"), _expr(n.expresion), pc))
    raise TypeError(f"Nodo no reconocido: {type(n).__name__}")


def _funcion(n: FuncionDecl):
    hijos = [_kw("funcion"), _t("IDENTIFICADOR", n.nombre), _t("PARENTESIS_IZQ", "(")]
    if n.parametros:
        params = []
        for i, p in enumerate(n.parametros):
            if i:
                params.append(_t("COMA", ","))
            params.append(_t("IDENTIFICADOR", p))
        hijos.append(_r("parametros", *params))
    hijos += [_t("PARENTESIS_DER", ")"), _bloque(n.cuerpo)]
    return _r("funcion_decl", *hijos)


def arbol_derivacion(programa: Programa) -> dict:
    """Arbol de derivacion (segun la BNF) del programa reconocido."""
    return _r("programa", *[
        _funcion(e) if isinstance(e, FuncionDecl) else _instruccion(e)
        for e in programa.elementos])


def arbol_a_texto(nodo: dict, sangria: int = 0) -> str:
    """Dibuja el arbol de derivacion con sangria, una linea por nodo."""
    pad = "  " * sangria
    if "token" in nodo:
        return f"{pad}{nodo['token']} {nodo['lexema']}"
    lineas = [f"{pad}{nodo['regla']}"]
    lineas += [arbol_a_texto(h, sangria + 1) for h in nodo["hijos"]]
    return "\n".join(lineas)


# --------------------- exportacion ---------------------
def parsear_codigo(codigo: str):
    """Lexer + parser. Devuelve (ast, errores_lexicos, errores_sintacticos)."""
    lexer = AnalizadorLexico(codigo)
    lexer.analizar()
    if lexer.errores:  # sin tokens validos completos no se parsea
        return None, lexer.errores, []
    ast, errores = parsear_tokens(lexer.tokens)
    return ast, [], errores


def exportar_syn(ast: Programa, errores: list, ruta_syn: str) -> None:
    """Escribe el .syn (JSON con exito, errores y ast) y, junto a el, el .der con el arbol de derivacion."""
    with open(ruta_syn, "w", encoding="utf-8") as f:
        json.dump({
            "exito": not errores,
            "total_errores": len(errores),
            "errores": [e.to_dict() for e in errores],
            "ast": ast.to_dict(),
        }, f, ensure_ascii=False, indent=2)
    ruta_der = os.path.splitext(ruta_syn)[0] + ".der"
    with open(ruta_der, "w", encoding="utf-8") as f:
        json.dump(arbol_derivacion(ast), f, ensure_ascii=False, indent=2)


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: python exportar_syn.py <entrada.pse|.txt> <salida.syn>")
        sys.exit(1)
    entrada, salida = sys.argv[1], sys.argv[2]
    try:
        with open(entrada, "r", encoding="utf-8") as f:
            codigo = f.read()
    except OSError as e:
        print(f"Error al leer el archivo de entrada: {e}")
        sys.exit(1)

    ast, err_lex, err_sin = parsear_codigo(codigo)
    if err_lex:
        print(f"Hay {len(err_lex)} error(es) léxico(s); corrige el léxico antes del análisis sintáctico.")
        sys.exit(2)
    exportar_syn(ast, err_sin, salida)
    if err_sin:
        print(f"Análisis sintáctico con {len(err_sin)} error(es). Ver {salida}")
        for e in err_sin:
            print(f"  {e.linea}:{e.columna} {e.mensaje}")
        sys.exit(3)
    print(f"Análisis sintáctico correcto: {salida} (AST) y {os.path.splitext(salida)[0]}.der (derivación)")


if __name__ == "__main__":
    main()
