"""
test_lexer.py - Pruebas de tokenizacion del analizador lexico (PIA Compiladores).

Uso:
    python test_lexer.py          (corre todas las pruebas)
    python test_lexer.py -v       (detalle de cada prueba)
"""
import unittest

from lexer import AnalizadorLexico


def escanear(codigo: str):
    a = AnalizadorLexico(codigo)
    a.analizar()
    return a.tokens, a.errores


def pares(codigo: str):
    """Lista de (tipo, lexema) sin errores."""
    tokens, errores = escanear(codigo)
    assert not errores, [e.mensaje for e in errores]
    return [(t.tipo, t.lexema) for t in tokens]


class PruebasValidas(unittest.TestCase):
    def test_v01_funcion_suma(self):
        codigo = "funcion suma(a, b) {\n    retornar a + b;\n}\n"
        self.assertEqual(pares(codigo), [
            ("PALABRA_CLAVE", "funcion"), ("IDENTIFICADOR", "suma"), ("PARENTESIS_IZQ", "("),
            ("IDENTIFICADOR", "a"), ("COMA", ","), ("IDENTIFICADOR", "b"), ("PARENTESIS_DER", ")"),
            ("LLAVE_IZQ", "{"), ("PALABRA_CLAVE", "retornar"), ("IDENTIFICADOR", "a"),
            ("OP_ARITMETICO", "+"), ("IDENTIFICADOR", "b"), ("PUNTOCOMA", ";"), ("LLAVE_DER", "}"),
        ])

    def test_v02_las_10_palabras_clave(self):
        palabras = "si sino mientras para funcion retornar leer escribir verdadero falso"
        self.assertEqual(
            pares(palabras), [("PALABRA_CLAVE", p) for p in palabras.split()])
        # inicio y fin ya no son palabras reservadas (la gramatica no las usa)
        self.assertEqual(pares("inicio fin"),
                         [("IDENTIFICADOR", "inicio"), ("IDENTIFICADOR", "fin")])

    def test_v03_numeros_validos(self):
        for lexema in ["0", "10", "3.14", "1.5e-3", "2E10", "7e+2", "100.0"]:
            with self.subTest(lexema=lexema):
                self.assertEqual(pares(lexema), [("NUMERO", lexema)])

    def test_v04_cadenas(self):
        self.assertEqual(pares('"hola"'), [("CADENA", '"hola"')])
        self.assertEqual(pares("'hola'"), [("CADENA", "'hola'")])
        self.assertEqual(pares('""'), [("CADENA", '""')])
        self.assertEqual(pares(r'"di \"hola\""'), [("CADENA", r'"di \"hola\""')])
        # las palabras clave y operadores dentro de una cadena no se separan
        self.assertEqual(pares('"si x == 1 // no es comentario"'),
                         [("CADENA", '"si x == 1 // no es comentario"')])

    def test_v05_operadores_relacionales_y_asignacion(self):
        self.assertEqual(
            pares("== != <= >= < > ="),
            [("OP_REL", "=="), ("OP_REL", "!="), ("OP_REL", "<="),
             ("OP_REL", ">="), ("OP_REL", "<"), ("OP_REL", ">"), ("OP_ASIGNACION", "=")])

    def test_v06_operadores_aritmeticos(self):
        self.assertEqual(pares("+ - * / %"), [("OP_ARITMETICO", c) for c in "+-*/%"])

    def test_v07_delimitadores(self):
        self.assertEqual(
            pares("( ) { } , ;"),
            [("PARENTESIS_IZQ", "("), ("PARENTESIS_DER", ")"), ("LLAVE_IZQ", "{"),
             ("LLAVE_DER", "}"), ("COMA", ","), ("PUNTOCOMA", ";")])

    def test_v08_identificadores(self):
        for lexema in ["x", "x1", "_tmp", "contador", "miVariable_2", "Si", "SINO", "funcion1"]:
            with self.subTest(lexema=lexema):
                self.assertEqual(pares(lexema), [("IDENTIFICADOR", lexema)])

    def test_v09_comentarios_se_descartan(self):
        self.assertEqual(pares("// solo comentario"), [])
        self.assertEqual(pares("x = 1; // fin de linea\ny = 2;"), [
            ("IDENTIFICADOR", "x"), ("OP_ASIGNACION", "="), ("NUMERO", "1"), ("PUNTOCOMA", ";"),
            ("IDENTIFICADOR", "y"), ("OP_ASIGNACION", "="), ("NUMERO", "2"), ("PUNTOCOMA", ";"),
        ])

    def test_v10_division_no_es_comentario(self):
        self.assertEqual(pares("a / b"), [
            ("IDENTIFICADOR", "a"), ("OP_ARITMETICO", "/"), ("IDENTIFICADOR", "b")])

    def test_v11_sin_espacios(self):
        self.assertEqual(pares("x=a+b*2;"), [
            ("IDENTIFICADOR", "x"), ("OP_ASIGNACION", "="), ("IDENTIFICADOR", "a"),
            ("OP_ARITMETICO", "+"), ("IDENTIFICADOR", "b"), ("OP_ARITMETICO", "*"),
            ("NUMERO", "2"), ("PUNTOCOMA", ";")])

    def test_v12_menos_unario_y_resta(self):
        self.assertEqual(pares("-5"), [("OP_ARITMETICO", "-"), ("NUMERO", "5")])
        self.assertEqual(pares("a-5"), [
            ("IDENTIFICADOR", "a"), ("OP_ARITMETICO", "-"), ("NUMERO", "5")])

    def test_v13_posicion_linea_y_columna(self):
        tokens, _ = escanear("x = 1;\n  si (x)")
        posiciones = [(t.lexema, t.linea, t.columna) for t in tokens]
        self.assertEqual(posiciones, [
            ("x", 1, 1), ("=", 1, 3), ("1", 1, 5), (";", 1, 6),
            ("si", 2, 3), ("(", 2, 6), ("x", 2, 7), (")", 2, 8)])

    def test_v14_saltos_de_linea_windows(self):
        tokens, _ = escanear("x = 1;\r\ny = 2;\r\n")
        self.assertEqual([(t.lexema, t.linea) for t in tokens if t.lexema in ("x", "y")],
                         [("x", 1), ("y", 2)])

    def test_v15_archivo_vacio(self):
        self.assertEqual(escanear(""), ([], []))
        self.assertEqual(escanear("  \n\t\n"), ([], []))


class PruebasConErrores(unittest.TestCase):
    def errores(self, codigo):
        _, errores = escanear(codigo)
        return [(e.linea, e.columna, e.mensaje) for e in errores]

    def test_e01_caracteres_no_reconocidos(self):
        self.assertEqual(self.errores("@ $ #"), [
            (1, 1, "Carácter no reconocido: '@'"),
            (1, 3, "Carácter no reconocido: '$'"),
            (1, 5, "Carácter no reconocido: '#'")])

    def test_e02_numeros_mal_formados(self):
        casos = {"3.": "3.", "2e": "2e", "7abc": "7abc", "1.2.3": "1.2.3", "5e+": "5e+", "9_9": "9_9"}
        for codigo, lexema in casos.items():
            with self.subTest(codigo=codigo):
                self.assertEqual(self.errores(codigo), [(1, 1, f"Número mal formado: '{lexema}'")])

    def test_e03_cadena_sin_cerrar(self):
        self.assertEqual(self.errores('x = "hola'), [(1, 5, 'Cadena sin cerrar: "hola')])
        self.assertEqual(self.errores("x = 'hola"), [(1, 5, "Cadena sin cerrar: 'hola")])

    def test_e04_cadena_sin_cerrar_no_contamina_la_linea_siguiente(self):
        tokens, errores = escanear('x = "hola; y\nz = 1;')
        self.assertEqual(len(errores), 1)
        self.assertEqual([t.lexema for t in tokens if t.linea == 2], ["z", "=", "1", ";"])

    def test_e05_varios_errores_se_reportan_todos(self):
        codigo = "x = 3.;\ny = @;\nz = \"abc;\nw = 7abc;\n"
        self.assertEqual(self.errores(codigo), [
            (1, 5, "Número mal formado: '3.'"),
            (2, 5, "Carácter no reconocido: '@'"),
            (3, 5, 'Cadena sin cerrar: "abc;'),
            (4, 5, "Número mal formado: '7abc'")])

    def test_e06_tras_un_error_sigue_tokenizando(self):
        tokens, errores = escanear("a = 1 @ 2;")
        self.assertEqual(len(errores), 1)
        self.assertEqual([t.lexema for t in tokens], ["a", "=", "1", "2", ";"])

    def test_e07_simbolos_fuera_del_lenguaje(self):
        for simbolo in ["!", "&", "|", "^", "[", "]", ".", ":", "?", "~"]:
            with self.subTest(simbolo=simbolo):
                self.assertEqual(self.errores(simbolo),
                                 [(1, 1, f"Carácter no reconocido: '{simbolo}'")])

    def test_e08_limitaciones_conocidas(self):
        # numeros que empiezan con punto: el '.' es error y el resto es un entero
        self.assertEqual(self.errores(".5"), [(1, 1, "Carácter no reconocido: '.'")])
        # las palabras clave distinguen mayusculas: 'Si' es un identificador, no un error
        self.assertEqual(self.errores("Si"), [])
        # letras con acento o ñ no son identificadores validos
        self.assertEqual(self.errores("año"), [(1, 2, "Carácter no reconocido: 'ñ'")])

    def test_e09_columna_con_tabulador(self):
        self.assertEqual(self.errores("\t@"), [(1, 2, "Carácter no reconocido: '@'")])


if __name__ == "__main__":
    unittest.main()
