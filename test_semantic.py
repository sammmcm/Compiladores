"""
test_semantic.py - Pruebas del analizador semantico (PIA Compiladores, Rol 4).

Uso:
    python test_semantic.py          (corre todas las pruebas)
    python test_semantic.py -v       (detalle de cada prueba)

Ademas corre los programas de ejemplo valido.pse, errores.pse y alcances.pse
si estan en la misma carpeta.
"""
import os
import unittest

from lexer import AnalizadorLexico
from parser import parsear_tokens
from semantic import analizar_semantica

CARPETA = os.path.dirname(os.path.abspath(__file__))


def analizar(codigo: str):
    """Corre lexico + sintactico + semantico. Devuelve (ast, errores, tabla)."""
    lex = AnalizadorLexico(codigo)
    lex.analizar()
    assert not lex.errores, [e.mensaje for e in lex.errores]
    ast, errores_sintacticos = parsear_tokens(lex.tokens)
    assert not errores_sintacticos, [e.mensaje for e in errores_sintacticos]
    errores, tabla = analizar_semantica(ast)
    return ast, errores, tabla


def errores(codigo: str):
    """Lista de (linea, mensaje) de los errores semanticos."""
    _, errs, _ = analizar(codigo)
    return [(e.linea, e.mensaje) for e in errs]


def tipo_global(codigo: str, nombre: str):
    _, errs, tabla = analizar(codigo)
    assert not errs, [e.mensaje for e in errs]
    return tabla["global"][nombre]["tipo"]


class PruebasTipos(unittest.TestCase):
    def test_t01_tipos_de_literales(self):
        self.assertEqual(tipo_global("x = 10;", "x"), "entero")
        self.assertEqual(tipo_global("x = 3.14;", "x"), "decimal")
        self.assertEqual(tipo_global("x = 1.5e-3;", "x"), "decimal")
        self.assertEqual(tipo_global('x = "hola";', "x"), "cadena")
        self.assertEqual(tipo_global("x = verdadero;", "x"), "booleano")

    def test_t02_aritmetica_entera_y_decimal(self):
        self.assertEqual(tipo_global("x = 2 + 3 * 4;", "x"), "entero")
        self.assertEqual(tipo_global("x = 2 + 1.5;", "x"), "decimal")
        self.assertEqual(tipo_global("x = 7 % 2;", "x"), "entero")

    def test_t03_division_siempre_decimal(self):
        self.assertEqual(tipo_global("x = 8 / 2;", "x"), "decimal")

    def test_t04_comparacion_da_booleano(self):
        self.assertEqual(tipo_global("x = 3 < 4.5;", "x"), "booleano")
        self.assertEqual(tipo_global('x = "a" == "b";', "x"), "booleano")
        self.assertEqual(tipo_global("x = verdadero != falso;", "x"), "booleano")

    def test_t05_menos_unario(self):
        self.assertEqual(tipo_global("x = -5;", "x"), "entero")
        self.assertEqual(tipo_global("x = -2.5;", "x"), "decimal")

    def test_t06_ensanchamiento_entero_a_decimal(self):
        self.assertEqual(tipo_global("d = 5; d = 2.5;", "d"), "decimal")
        self.assertEqual(tipo_global("d = 2.5; d = 5;", "d"), "decimal")

    def test_t07_leer_es_indeterminado_y_contagia(self):
        self.assertEqual(tipo_global("leer(n);", "n"), "indeterminado")
        self.assertEqual(tipo_global("t = 0; leer(n); t = t + n;", "t"), "indeterminado")

    def test_t08_condiciones_validas(self):
        codigo = (
            "x = 1;\n"
            "si (x < 10) { x = x + 1; } sino { x = 0; }\n"
            "mientras (x > 0) { x = x - 1; }\n"
            "para (i = 0; i < 3; i = i + 1) { escribir(i); }\n"
        )
        self.assertEqual(errores(codigo), [])


class PruebasAlcances(unittest.TestCase):
    def test_a01_funcion_lee_global(self):
        codigo = "g = 5;\nfuncion f() {\n    retornar g + 1;\n}\nx = f();"
        self.assertEqual(errores(codigo), [])

    def test_a02_parametros_son_locales(self):
        _, errs, tabla = analizar("funcion suma(a, b) {\n    retornar a + b;\n}")
        self.assertEqual(errs, [])
        locales = tabla["funciones"]["suma"]["variables_locales"]
        self.assertEqual(set(locales), {"a", "b"})
        self.assertEqual(locales["a"]["tipo"], "indeterminado")
        self.assertNotIn("a", tabla["global"])

    def test_a03_local_oculta_global(self):
        codigo = 'x = 10;\nfuncion f() {\n    x = "local";\n    retornar x;\n}'
        _, errs, tabla = analizar(codigo)
        self.assertEqual(errs, [])
        self.assertEqual(tabla["global"]["x"]["tipo"], "entero")
        self.assertEqual(tabla["funciones"]["f"]["variables_locales"]["x"]["tipo"], "cadena")

    def test_a04_local_no_visible_afuera(self):
        codigo = "funcion f() {\n    loc = 1;\n    retornar loc;\n}\nescribir(loc);"
        self.assertEqual(errores(codigo), [(5, "Variable 'loc' no declarada")])

    def test_a05_bloques_no_crean_alcance(self):
        codigo = "si (verdadero) { dentro = 1; }\nescribir(dentro);"
        self.assertEqual(errores(codigo), [])

    def test_a06_llamar_antes_de_definir(self):
        codigo = "x = doble(2);\nfuncion doble(a) {\n    retornar a * 2;\n}"
        self.assertEqual(errores(codigo), [])

    def test_a07_cuenta_usos(self):
        _, _, tabla = analizar("x = 1;\ny = x + x;\nescribir(x);")
        self.assertEqual(tabla["global"]["x"]["usos"], 3)
        self.assertEqual(tabla["global"]["y"]["usos"], 0)

    def test_a08_anotaciones_en_el_ast(self):
        ast, _, _ = analizar("n = 3;")
        asignacion = ast.elementos[0]
        self.assertEqual(asignacion.anotaciones,
                         {"scope": "global", "tipo_variable": "entero", "nueva_declaracion": True})
        self.assertEqual(asignacion.expresion.anotaciones["tipo_inferido"], "entero")


class PruebasErrores(unittest.TestCase):
    def test_e01_variable_no_declarada(self):
        self.assertEqual(errores("escribir(y);"), [(1, "Variable 'y' no declarada")])

    def test_e02_funcion_no_declarada(self):
        self.assertEqual(errores("r = cubo(2);"), [(1, "Función 'cubo' no declarada")])

    def test_e03_numero_de_argumentos(self):
        codigo = "funcion doble(a) {\n    retornar a * 2;\n}\nr = doble(1, 2);"
        self.assertEqual(errores(codigo),
                         [(4, "'doble' esperaba 1 argumento(s) pero recibió 2")])

    def test_e04_funcion_repetida(self):
        codigo = "funcion f() {\n    retornar 1;\n}\nfuncion f() {\n    retornar 2;\n}"
        self.assertEqual(errores(codigo),
                         [(4, "Función 'f' ya fue declarada en la línea 1")])

    def test_e05_parametro_repetido(self):
        codigo = "funcion f(a, a) {\n    retornar a;\n}"
        self.assertEqual(errores(codigo),
                         [(1, "Parámetro 'a' repetido en la función 'f'")])

    def test_e06_cambio_de_tipo(self):
        self.assertEqual(errores('edad = 20;\nedad = "veinte";'), [
            (2, "No se puede asignar un valor 'cadena' a 'edad', que es de tipo 'entero'")])

    def test_e07_operando_no_numerico(self):
        self.assertEqual(errores('x = "hola" * 2;'), [
            (1, "Se esperaba un tipo numérico en el operando izquierdo de '*', se obtuvo 'cadena'")])
        self.assertEqual(errores("x = 1 + verdadero;"), [
            (1, "Se esperaba un tipo numérico en el operando derecho de '+', se obtuvo 'booleano'")])
        self.assertEqual(errores('x = -"a";'), [
            (1, "Se esperaba un tipo numérico en el operador unario '-', se obtuvo 'cadena'")])

    def test_e08_condicion_no_booleana(self):
        casos = {
            "si (1) { x = 1; }": "si",
            "mientras (1) { x = 1; }": "mientras",
            "para (i = 0; i; i = i + 1) { x = 1; }": "para",
        }
        for codigo, palabra in casos.items():
            with self.subTest(palabra=palabra):
                self.assertEqual(errores(codigo), [
                    (1, f"Se esperaba una expresión booleana en la condición de '{palabra}', se obtuvo 'entero'")])

    def test_e09_comparacion_incompatible(self):
        self.assertEqual(errores('c = "a" == 1;'), [
            (1, "Comparación '==' entre tipos incompatibles: 'cadena' y 'entero'")])

    def test_e10_orden_entre_booleanos(self):
        self.assertEqual(errores("ok = verdadero < falso;"), [
            (1, "Los booleanos solo se pueden comparar con '==' o '!=', no con '<'")])

    def test_e11_division_entre_cero(self):
        self.assertEqual(errores("x = 5 / 0;"), [(1, "División entre cero con el operador '/'")])
        self.assertEqual(errores("x = 5 % 0;"), [(1, "División entre cero con el operador '%'")])

    def test_e12_retornar_fuera_de_funcion(self):
        self.assertEqual(errores("retornar 1;"), [(1, "'retornar' usado fuera de una función")])

    def test_e13_sin_errores_en_cascada(self):
        # y no existe: solo un error, aunque z y w dependan de ella
        self.assertEqual(errores("z = y + 1;\nw = z * 2;\nescribir(w);"),
                         [(1, "Variable 'y' no declarada")])

    def test_e14_varios_errores_se_reportan_todos(self):
        codigo = 'a = "x" * 2;\nb = c;\nretornar 1;'
        self.assertEqual(len(errores(codigo)), 3)


class PruebasProgramasDeEjemplo(unittest.TestCase):
    """Los tres programas de la seccion 5 del documento."""

    def correr(self, archivo):
        ruta = os.path.join(CARPETA, archivo)
        if not os.path.exists(ruta):
            self.skipTest(f"no se encontró {archivo}")
        with open(ruta, encoding="utf-8") as f:
            return errores(f.read())

    def test_p01_valido(self):
        self.assertEqual(self.correr("valido.pse"), [])

    def test_p02_errores_de_tipos(self):
        self.assertEqual([l for l, _ in self.correr("errores.pse")],
                         [3, 4, 5, 6, 8, 9, 10, 14, 15])

    def test_p03_errores_de_alcance(self):
        self.assertEqual(self.correr("alcances.pse"), [
            (7, "Función 'f' ya fue declarada en la línea 2"),
            (2, "Parámetro 'a' repetido en la función 'f'"),
            (10, "Variable 'local' no declarada"),
            (11, "Variable 'y' no declarada"),
        ])


if __name__ == "__main__":
    unittest.main()
