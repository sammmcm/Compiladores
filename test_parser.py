"""
test_parser.py - Pruebas del analizador sintactico (PIA Compiladores).

Uso:
    python test_parser.py          (corre todas las pruebas)
    python test_parser.py -v       (detalle de cada prueba)
"""
import json
import os
import tempfile
import unittest

from lexer import AnalizadorLexico
from parser import parsear_tokens
from exportar_syn import arbol_derivacion, exportar_syn, parsear_codigo

_AQUI = os.path.dirname(os.path.abspath(__file__))
# los .pse pueden estar en ejemplos/ o en la misma carpeta que este archivo
CARPETA_EJEMPLOS = os.path.join(_AQUI, "ejemplos")
if not os.path.isdir(CARPETA_EJEMPLOS):
    CARPETA_EJEMPLOS = _AQUI


def analizar(codigo: str):
    """Lexer + parser. Devuelve (ast, errores_sintacticos). El lexico debe estar limpio."""
    ast, err_lex, err_sin = parsear_codigo(codigo)
    assert not err_lex, [e.mensaje for e in err_lex]
    return ast, err_sin


def expr(codigo: str) -> dict:
    """AST (como diccionario) de la expresion de `x = <codigo>;`."""
    ast, errores = analizar(f"x = {codigo};")
    assert not errores, [e.mensaje for e in errores]
    return ast.to_dict()["elementos"][0]["expresion"]


def forma(nodo: dict) -> str:
    """Notacion con parentesis de una expresion, para ver como se agrupo."""
    t = nodo["tipo"]
    if t == "OperacionBinaria":
        return f"({forma(nodo['izquierda'])} {nodo['operador']} {forma(nodo['derecha'])})"
    if t == "OperacionUnaria":
        return f"(-{forma(nodo['operando'])})"
    if t == "LlamadaFuncion":
        return f"{nodo['nombre']}({', '.join(forma(a) for a in nodo['argumentos'])})"
    if t == "Literal":
        return repr(nodo["valor"])
    return nodo["nombre"]


def tipos(codigo: str):
    """Tipos de los elementos de primer nivel, sin errores."""
    ast, errores = analizar(codigo)
    assert not errores, [e.mensaje for e in errores]
    return [e["tipo"] for e in ast.to_dict()["elementos"]]


def hojas(nodo: dict):
    if "token" in nodo:
        return [nodo["lexema"]]
    return [h for hijo in nodo["hijos"] for h in hojas(hijo)]


FACTORIAL = (
    "// Calcula el factorial y lo imprime\n"
    "funcion factorial(n) {\n    r = 1;\n    para (i = 1; i <= n; i = i + 1) {\n"
    "        r = r * i;\n    }\n    retornar r;\n}\n\n"
    "x = 5;\nescribir(\"Factorial: \");\nescribir(factorial(x));\n")


class PruebasValidas(unittest.TestCase):
    def test_v01_asignacion(self):
        ast, errores = analizar("x = 5;")
        self.assertEqual(errores, [])
        self.assertEqual(ast.to_dict(), {"tipo": "Programa", "elementos": [{
            "tipo": "Asignacion", "identificador": "x", "linea": 1,
            "expresion": {"tipo": "Literal", "tipo_valor": "entero", "valor": 5, "linea": 1}}]})

    def test_v02_precedencia_mult_sobre_suma(self):
        self.assertEqual(forma(expr("1 + 2 * 3 - 4")), "((1 + (2 * 3)) - 4)")

    def test_v03_asociatividad_izquierda(self):
        self.assertEqual(forma(expr("a - b - c")), "((a - b) - c)")
        self.assertEqual(forma(expr("a / b * c")), "((a / b) * c)")

    def test_v04_parentesis_cambian_el_orden(self):
        self.assertEqual(forma(expr("(1 + 2) * 3")), "((1 + 2) * 3)")

    def test_v05_menos_unario_y_llamada(self):
        self.assertEqual(forma(expr("-f(x)")), "(-f(x))")
        self.assertEqual(forma(expr("- -a")), "(-(-a))")
        self.assertEqual(forma(expr("a * -b")), "(a * (-b))")

    def test_v06_comparacion_es_la_mas_baja(self):
        self.assertEqual(forma(expr("a + 1 <= b * 2")), "((a + 1) <= (b * 2))")

    def test_v07_literales(self):
        ast, _ = analizar('a = 3.5; b = "hola"; c = verdadero; d = 1.5e-3;')
        tipos_valor = [e["expresion"]["tipo_valor"] for e in ast.to_dict()["elementos"]]
        self.assertEqual(tipos_valor, ["decimal", "cadena", "booleano", "decimal"])

    def test_v08_funcion_con_parametros(self):
        ast, errores = analizar("funcion suma(a, b) {\n    retornar a + b;\n}\n")
        self.assertEqual(errores, [])
        f = ast.to_dict()["elementos"][0]
        self.assertEqual((f["tipo"], f["nombre"], f["parametros"]), ("FuncionDecl", "suma", ["a", "b"]))
        self.assertEqual(f["cuerpo"][0]["tipo"], "Retornar")

    def test_v09_funcion_sin_parametros(self):
        ast, errores = analizar("funcion hola() { escribir(\"hola\"); }")
        self.assertEqual(errores, [])
        self.assertEqual(ast.to_dict()["elementos"][0]["parametros"], [])

    def test_v10_si_con_y_sin_sino(self):
        ast, _ = analizar("si (x > 1) { y = 1; } sino { y = 2; }\nsi (x) { y = 3; }")
        a, b = ast.to_dict()["elementos"]
        self.assertEqual(len(a["bloque_sino"]), 1)
        self.assertIsNone(b["bloque_sino"])

    def test_v11_mientras(self):
        self.assertEqual(tipos("mientras (x < 3) { x = x + 1; }"), ["Mientras"])

    def test_v12_para(self):
        ast, errores = analizar("para (i = 0; i < 3; i = i + 1) { escribir(i); }")
        self.assertEqual(errores, [])
        p = ast.to_dict()["elementos"][0]
        self.assertEqual([p["inicializacion"]["tipo"], p["condicion"]["tipo"], p["incremento"]["tipo"]],
                         ["Asignacion", "OperacionBinaria", "Asignacion"])

    def test_v13_leer_escribir_retornar(self):
        self.assertEqual(tipos("leer(x);\nescribir(x + 1);"), ["Leer", "Escribir"])

    def test_v14_llamada_como_instruccion_y_anidada(self):
        self.assertEqual(tipos("suma(1, 2);"), ["LlamadaFuncion"])
        self.assertEqual(forma(expr("f(g(1), 2)")), "f(g(1), 2)")

    def test_v15_llamada_antes_de_su_definicion(self):
        self.assertEqual(tipos("escribir(doble(2));\nfuncion doble(n) { retornar n * 2; }"),
                         ["Escribir", "FuncionDecl"])

    def test_v16_if_anidado_en_sino(self):
        ast, errores = analizar("si (a) { x = 1; } sino { si (b) { x = 2; } }")
        self.assertEqual(errores, [])
        self.assertEqual(ast.to_dict()["elementos"][0]["bloque_sino"][0]["tipo"], "Si")

    def test_v17_programa_vacio(self):
        ast, errores = analizar("")
        self.assertEqual((ast.elementos, errores), ([], []))
        ast, errores = analizar("// solo un comentario\n")
        self.assertEqual((ast.elementos, errores), ([], []))

    def test_v18_factorial_completo(self):
        ast, errores = analizar(FACTORIAL)
        self.assertEqual(errores, [])
        self.assertEqual([e["tipo"] for e in ast.to_dict()["elementos"]],
                         ["FuncionDecl", "Asignacion", "Escribir", "Escribir"])

    def test_v19_lineas_en_el_ast(self):
        ast, _ = analizar("x = 1;\n\ny = 2;")
        self.assertEqual([e["linea"] for e in ast.to_dict()["elementos"]], [1, 3])


class PruebasArbolDerivacion(unittest.TestCase):
    def test_d01_las_hojas_son_los_tokens_del_programa(self):
        lexer = AnalizadorLexico(FACTORIAL)
        lexer.analizar()
        ast, errores = parsear_tokens(lexer.tokens)
        self.assertEqual(errores, [])
        self.assertEqual(hojas(arbol_derivacion(ast)), [t.lexema for t in lexer.tokens])

    def test_d02_raiz_y_reglas(self):
        ast, _ = analizar("x = 1;")
        arbol = arbol_derivacion(ast)
        self.assertEqual(arbol["regla"], "programa")
        instruccion = arbol["hijos"][0]
        self.assertEqual(instruccion["regla"], "instruccion")
        self.assertEqual([h.get("regla") or h["token"] for h in instruccion["hijos"]],
                         ["asignacion", "PUNTOCOMA"])

    def test_d03_precedencia_se_ve_en_el_arbol(self):
        # 1 + 2 * 3: la multiplicacion queda dentro de un 'termino' hijo de 'suma'
        ast, _ = analizar("x = 1 + 2 * 3;")
        suma = arbol_derivacion(ast)["hijos"][0]["hijos"][0]["hijos"][2]
        while suma["regla"] != "suma":
            suma = suma["hijos"][0]
        self.assertEqual([h.get("regla") or h["lexema"] for h in suma["hijos"]],
                         ["termino", "+", "termino"])
        self.assertIn("*", hojas(suma["hijos"][2]))

    def test_d04_parentesis_necesarios_reaparecen(self):
        ast, _ = analizar("x = (1 + 2) * 3;")
        self.assertEqual(hojas(arbol_derivacion(ast)), ["x", "=", "(", "1", "+", "2", ")", "*", "3", ";"])

    def test_d05_programa_vacio(self):
        ast, _ = analizar("")
        self.assertEqual(arbol_derivacion(ast), {"regla": "programa", "hijos": []})


class PruebasConErrores(unittest.TestCase):
    def errores(self, codigo):
        _, errores = analizar(codigo)
        return [(e.linea, e.columna, e.mensaje) for e in errores]

    def test_e01_punto_y_coma_faltante(self):
        self.assertEqual(self.errores("x = 5\nescribir(x);"),
                         [(1, 6, "Falta ';' al final de la instrucción")])

    def test_e02_punto_y_coma_faltante_al_final_del_archivo(self):
        self.assertEqual(self.errores("x = 5"), [(1, 6, "Falta ';' al final de la instrucción")])

    def test_e03_falta_parentesis_de_cierre(self):
        self.assertEqual(self.errores("x = 10;\nsi (x > 5 {\n    escribir(x);\n}"),
                         [(2, 11, "Se esperaba ')' pero se encontró '{'")])

    def test_e04_falta_operando(self):
        self.assertEqual(self.errores("b = 3 + ;"), [(1, 9, (
            "Falta un operando: se esperaba un número, identificador, cadena o '(' "
            "pero se encontró ';'"))])

    def test_e05_expresion_al_final_del_archivo(self):
        (_, _, mensaje), = self.errores("x =")
        self.assertTrue(mensaje.endswith("pero se encontró el fin del archivo"))

    def test_e06_bloque_sin_cerrar(self):
        self.assertEqual(self.errores("funcion f(n) {\n    retornar n;\n"),
                         [(1, 14, "Bloque sin cerrar: la '{' de la línea 1 no tiene su '}'")])

    def test_e07_instruccion_invalida(self):
        self.assertEqual(self.errores("5 + 3;"),
                         [(1, 1, "Instrucción inválida, token inesperado '5'")])

    def test_e08_instruccion_sin_efecto(self):
        self.assertEqual(self.errores("x + 1;"), [(1, 1, (
            "Instrucción sin efecto: se esperaba una asignación o una llamada a función"))])

    def test_e09_no_existe_sino_si(self):
        self.assertEqual(self.errores("si (a) { x = 1; } sino si (b) { x = 2; }"),
                         [(1, 24, "Se esperaba '{' pero se encontró 'si'")])

    def test_e10_para_con_partes_vacias(self):
        # el primer error es el real; los siguientes son en cascada por la recuperacion
        self.assertEqual(self.errores("para (; i < 3; i = i + 1) { x = 1; }")[0],
                         (1, 7, "Se esperaba un identificador pero se encontró ';'"))

    def test_e11_parametro_invalido(self):
        self.assertEqual(self.errores("funcion f(1) { retornar 1; }"),
                         [(1, 11, "Se esperaba un identificador pero se encontró '1'")])

    def test_e12_solo_un_identificador_se_invoca(self):
        self.assertEqual(self.errores("x = f(1)(2);"),
                         [(1, 9, "Solo un identificador puede invocarse como función")])

    def test_e13_falta_igual_en_para(self):
        self.assertEqual(self.errores("para (i 0; i < 3; i = i + 1) { }")[0],
                         (1, 9, "Se esperaba '=' pero se encontró '0'"))

    def test_e14_varios_errores_se_reportan_todos(self):
        codigo = "x = 5\nescribir(x);\ny = 3 + ;\nsi (x > 2 {\n    escribir(\"a\");\n}\nz = 1;\n"
        self.assertEqual([(l, c) for l, c, _ in self.errores(codigo)], [(1, 6), (3, 9), (4, 11)])

    def test_e15_tras_un_error_se_conserva_lo_demas(self):
        ast, errores = analizar("y = (2 + 3;\nz = 1;\nescribir(z);")
        self.assertEqual(len(errores), 1)
        self.assertEqual([e["tipo"] for e in ast.to_dict()["elementos"]], ["Asignacion", "Escribir"])

    def test_e16_error_dentro_de_un_bloque_no_rompe_el_bloque(self):
        ast, errores = analizar("mientras (x < 3) {\n    y = 1 +;\n    x = x + 1;\n}\nescribir(x);")
        self.assertEqual(len(errores), 1)
        elementos = ast.to_dict()["elementos"]
        self.assertEqual([e["tipo"] for e in elementos], ["Mientras", "Escribir"])
        self.assertEqual(len(elementos[0]["cuerpo"]), 1)  # solo sobrevive 'x = x + 1;'

    def test_e17_los_errores_son_de_fase_sintactica(self):
        _, errores = analizar("x = 5\n")
        self.assertEqual([e.fase for e in errores], ["sintactico"])


class PruebasExportacion(unittest.TestCase):
    def exportar(self, codigo):
        ast, errores = analizar(codigo)
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "salida.syn")
            exportar_syn(ast, errores, ruta)
            with open(ruta, encoding="utf-8") as f:
                syn = json.load(f)
            with open(os.path.join(carpeta, "salida.der"), encoding="utf-8") as f:
                der = json.load(f)
        return syn, der

    def test_x01_syn_sin_errores(self):
        syn, der = self.exportar(FACTORIAL)
        self.assertEqual(list(syn), ["exito", "total_errores", "errores", "ast"])
        self.assertTrue(syn["exito"])
        self.assertEqual((syn["total_errores"], syn["errores"]), (0, []))
        self.assertEqual(syn["ast"]["tipo"], "Programa")
        self.assertEqual(der["regla"], "programa")

    def test_x02_syn_con_errores(self):
        syn, _ = self.exportar("x = 5\nescribir(x);")
        self.assertFalse(syn["exito"])
        self.assertEqual(syn["total_errores"], 1)
        self.assertEqual(syn["errores"][0], {
            "fase": "sintactico", "linea": 1, "mensaje": "Falta ';' al final de la instrucción",
            "columna": 6})
        self.assertEqual(syn["ast"]["elementos"][0]["tipo"], "Escribir")

    def test_x03_errores_lexicos_impiden_parsear(self):
        ast, err_lex, err_sin = parsear_codigo("x = 3.;")
        self.assertIsNone(ast)
        self.assertEqual((len(err_lex), err_sin), (1, []))


class PruebasEjemplos(unittest.TestCase):
    """Los archivos .pse de la carpeta ejemplos/ producen los errores esperados."""
    ESPERADO = {
        "valido.pse": [],
        "err_puntocoma.pse": [(1, 6)],
        "err_parentesis.pse": [(2, 11)],
        "err_operando.pse": [(2, 9)],
        "err_llave.pse": [(1, 18)],
        "err_varios.pse": [(1, 6), (3, 9), (4, 11)],
    }

    def test_ejemplos(self):
        for nombre, esperado in self.ESPERADO.items():
            with self.subTest(archivo=nombre):
                with open(os.path.join(CARPETA_EJEMPLOS, nombre), encoding="utf-8") as f:
                    _, errores = analizar(f.read())
                self.assertEqual([(e.linea, e.columna) for e in errores], esperado)


if __name__ == "__main__":
    unittest.main()
