"""
test_tac.py - Pruebas del codigo intermedio (TAC), el optimizador y el interprete (PIA Compiladores).

Uso:
    python test_tac.py          (corre todas las pruebas)
    python test_tac.py -v       (detalle de cada prueba)
"""
import contextlib
import io
import json
import os
import tempfile
import unittest

from lexer import AnalizadorLexico
from parser import parsear_tokens
from semantic import analizar_semantica
from tac import GeneradorTAC, optimizar, ejecutar, listar, exportar_tac
from main import compilar

FACTORIAL = '''// Calcula el factorial y lo imprime
funcion factorial(n) {
    r = 1;
    para (i = 1; i <= n; i = i + 1) {
        r = r * i;
    }
    retornar r;
}

x = 5;
escribir("Factorial: ");
escribir(factorial(x));
'''

OPTIMIZACION = '''base = 4 * 2;
altura = base + 2;
area = base * altura / 2;
si (base > 100) {
    escribir("nunca pasa");
}
escribir(area);
contador = 0;
mientras (contador < 3) {
    contador = contador + 1;
}
escribir(contador);
'''


def generar(codigo: str):
    """Fuente -> (TAC original, TAC optimizado). El programa debe ser valido en las 3 fases."""
    lx = AnalizadorLexico(codigo)
    lx.analizar()
    assert not lx.errores, [e.mensaje for e in lx.errores]
    ast, err_sin = parsear_tokens(lx.tokens)
    assert not err_sin, [e.mensaje for e in err_sin]
    err_sem, _ = analizar_semantica(ast)
    assert not err_sem, [e.mensaje for e in err_sem]
    tac = GeneradorTAC().generar(ast)
    return tac, optimizar(tac)


def lineas(codigo_tac):
    """El TAC como lista de lineas de texto, sin la sangria."""
    return [str(c).strip() for c in codigo_tac]


def correr(codigo_tac, entrada=None):
    """Ejecuta el TAC y devuelve lo que escribio, como lista."""
    salida = []
    ejecutar(codigo_tac, entrada=entrada if entrada is not None else [], salida=salida.append)
    return salida


class PruebasGenerador(unittest.TestCase):
    def test_g01_asignacion(self):
        tac, _ = generar("x = 5;")
        self.assertEqual(lineas(tac), ["func main():", "x = 5", "endfunc"])

    def test_g02_precedencia_en_expresion(self):
        # el * se calcula antes que el +
        tac, _ = generar("a = 1; b = 2; x = a + b * 2;")
        self.assertEqual(lineas(tac)[3:6], ["t1 = b * 2", "t2 = a + t1", "x = t2"])

    def test_g02b_operando_izquierdo_se_evalua_primero(self):
        # los dos lados generan codigo: el temporal del izquierdo debe salir antes
        tac, _ = generar("a = 1; b = 2; x = (a + 1) * (b + 2);")
        self.assertEqual(lineas(tac)[3:7], ["t1 = a + 1", "t2 = b + 2", "t3 = t1 * t2", "x = t3"])

    def test_g03_menos_unario(self):
        tac, _ = generar("a = 3; b = -a;")
        self.assertIn("t1 = - a", lineas(tac))

    def test_g04_si_sin_sino(self):
        tac, _ = generar("x = 1; si (x > 0) { escribir(x); }")
        self.assertEqual(lineas(tac)[2:], [
            "t1 = x > 0", "if_false t1 goto L1", "write x", "L1:", "endfunc"])

    def test_g05_si_con_sino(self):
        tac, _ = generar("x = 1; si (x > 0) { escribir(1); } sino { escribir(2); }")
        self.assertEqual(lineas(tac)[2:], [
            "t1 = x > 0", "if_false t1 goto L1", "write 1", "goto L2",
            "L1:", "write 2", "L2:", "endfunc"])

    def test_g06_mientras(self):
        tac, _ = generar("i = 0; mientras (i < 3) { i = i + 1; }")
        self.assertEqual(lineas(tac)[2:], [
            "L1:", "t1 = i < 3", "if_false t1 goto L2", "t2 = i + 1", "i = t2",
            "goto L1", "L2:", "endfunc"])

    def test_g07_para(self):
        tac, _ = generar("para (i = 0; i < 2; i = i + 1) { escribir(i); }")
        self.assertEqual(lineas(tac)[1:], [
            "i = 0", "L1:", "t1 = i < 2", "if_false t1 goto L2", "write i",
            "t2 = i + 1", "i = t2", "goto L1", "L2:", "endfunc"])

    def test_g08_funcion_con_retorno_implicito(self):
        # main va primero y despues cada funcion; todas terminan con return 0 implicito
        tac, _ = generar("funcion doble(n) { retornar n * 2; } x = doble(4);")
        self.assertEqual(lineas(tac), [
            "func main():", "param 4", "t1 = call doble, 1", "x = t1", "endfunc",
            "func doble(n):", "t2 = n * 2", "return t2", "return 0", "endfunc"])

    def test_g09_llamada_evalua_argumentos_antes_de_param(self):
        tac, _ = generar("funcion f(a, b) { retornar a; } x = f(1 + 2, 3);")
        main = lineas(tac)[:lineas(tac).index("endfunc") + 1]
        self.assertEqual(main[1:], ["t1 = 1 + 2", "param t1", "param 3", "t2 = call f, 2", "x = t2", "endfunc"])

    def test_g10_llamada_como_instruccion_sin_resultado(self):
        tac, _ = generar("funcion f(a) { retornar a; } f(1);")
        self.assertIn("call f, 1", lineas(tac))

    def test_g11_leer_y_escribir(self):
        tac, _ = generar('leer(n); escribir("hola"); escribir(n);')
        self.assertEqual(lineas(tac)[1:-1], ["read n", 'write "hola"', "write n"])

    def test_g12_factorial(self):
        tac, _ = generar(FACTORIAL)
        self.assertEqual(len(tac), 22)
        self.assertEqual(lineas(tac)[0], "func main():")
        self.assertEqual(lineas(tac).count("endfunc"), 2)


class PruebasOptimizador(unittest.TestCase):
    def test_o01_plegado_de_constantes(self):
        _, opt = generar("x = 2 + 3 * 4;")
        self.assertEqual(lineas(opt), ["func main():", "x = 14", "endfunc"])

    def test_o02_propagacion_de_constantes(self):
        _, opt = generar("a = 4; b = a * 2; escribir(b);")
        self.assertEqual(lineas(opt)[-2], "write 8")

    def test_o03_condicion_siempre_verdadera_quita_el_salto(self):
        _, opt = generar('si (1 < 2) { escribir("si"); }')
        self.assertEqual(lineas(opt), ["func main():", 'write "si"', "endfunc"])

    def test_o04_condicion_siempre_falsa_quita_el_bloque(self):
        _, opt = generar('si (3 < 2) { escribir("nunca"); } escribir("fin");')
        self.assertEqual(lineas(opt), ["func main():", 'write "fin"', "endfunc"])

    def test_o05_division_entre_cero_no_se_pliega(self):
        # el error debe verse al ejecutar, no desaparecer al optimizar
        _, opt = generar("z = 0; x = 1 / z; escribir(x);")
        self.assertTrue(any("/" in t for t in lineas(opt)))
        with self.assertRaises(ZeroDivisionError):
            correr(opt)

    def test_o06_no_propaga_a_traves_de_un_ciclo(self):
        # contador cambia dentro del ciclo: no puede reemplazarse por 0
        _, opt = generar("c = 0; mientras (c < 3) { c = c + 1; } escribir(c);")
        texto = lineas(opt)
        # se revisa la estructura antes de ejecutar, para que un error no deje un ciclo infinito
        self.assertIn("L1:", texto)
        self.assertIn("t1 = c < 3", texto)
        self.assertEqual(correr(opt), [3])

    def test_o07_codigo_despues_de_return_se_elimina(self):
        tac, opt = generar("funcion f() { retornar 1; escribir(2); } x = f();")
        self.assertIn("write 2", lineas(tac))
        self.assertNotIn("write 2", lineas(opt))

    def test_o08_ejemplo_de_la_documentacion_23_a_15(self):
        tac, opt = generar(OPTIMIZACION)
        self.assertEqual((len(tac), len(opt)), (23, 15))

    def test_o09_factorial_pierde_el_return_inalcanzable(self):
        tac, opt = generar(FACTORIAL)
        self.assertEqual((len(tac), len(opt)), (22, 21))

    def test_o10_nunca_agrega_instrucciones(self):
        for fuente in (FACTORIAL, OPTIMIZACION, "x = 1;", "a = 1; si (a > 0) { escribir(a); }"):
            with self.subTest(fuente=fuente[:20]):
                tac, opt = generar(fuente)
                self.assertLessEqual(len(opt), len(tac))


class PruebasInterprete(unittest.TestCase):
    def igual_original_y_optimizado(self, fuente, esperado, entrada=None):
        tac, opt = generar(fuente)
        self.assertEqual(correr(tac, entrada), esperado)
        self.assertEqual(correr(opt, entrada), esperado)

    def test_i01_factorial(self):
        self.igual_original_y_optimizado(FACTORIAL, ["Factorial: ", 120])

    def test_i02_si_sino(self):
        fuente = "x = 3; si (x > 5) { escribir(\"grande\"); } sino { escribir(\"chico\"); }"
        self.igual_original_y_optimizado(fuente, ["chico"])

    def test_i03_ciclo_para(self):
        self.igual_original_y_optimizado(
            "s = 0; para (i = 1; i <= 4; i = i + 1) { s = s + i; } escribir(s);", [10])

    def test_i04_recursion(self):
        fuente = ("funcion fib(n) { si (n < 2) { retornar n; } retornar fib(n - 1) + fib(n - 2); }"
                  " escribir(fib(10));")
        self.igual_original_y_optimizado(fuente, [55])

    def test_i05_division_siempre_da_decimal(self):
        self.igual_original_y_optimizado("escribir(7 / 2); escribir(6 / 3);", [3.5, 2.0])

    def test_i06_booleanos_se_escriben_en_espanol(self):
        self.igual_original_y_optimizado("a = 3; escribir(a > 1); escribir(a > 5);", ["verdadero", "falso"])

    def test_i07_leer_toma_los_valores_de_la_entrada(self):
        self.igual_original_y_optimizado("leer(n); leer(m); escribir(n * m);", [12], entrada=[3, 4])

    def test_i08_funcion_no_ve_variables_de_main_como_locales(self):
        fuente = "funcion suma(a, b) { retornar a + b; } r = suma(2, 3); escribir(r);"
        self.igual_original_y_optimizado(fuente, [5])

    def test_i09_division_entre_cero_en_ejecucion(self):
        tac, opt = generar("a = 5; b = a - 5; escribir(10 / b);")
        for codigo in (tac, opt):
            with self.assertRaises(ZeroDivisionError):
                correr(codigo)

    def test_i10_leer_sin_valores_suficientes(self):
        tac, _ = generar("leer(n); escribir(n);")
        with self.assertRaises(IndexError):
            correr(tac, entrada=[])


class PruebasExportacion(unittest.TestCase):
    def test_x01_formato_del_json(self):
        tac, _ = generar("funcion f(a) { retornar a; } x = 5; escribir(f(x));")
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "salida.tac")
            exportar_tac(tac, ruta)
            with open(ruta, encoding="utf-8") as f:
                datos = json.load(f)
        self.assertTrue(datos["exito"])
        self.assertEqual(datos["total_instrucciones"], len(tac))
        self.assertEqual(len(datos["instrucciones"]), len(tac))
        primera = datos["instrucciones"][0]
        self.assertEqual((primera["indice"], primera["op"], primera["arg1"], primera["arg2"]),
                         (1, "func", "main", []))
        # las constantes se distinguen de los nombres de variable
        asignacion = next(i for i in datos["instrucciones"] if i["res"] == "x")
        self.assertEqual(asignacion["arg1"], {"constante": 5})
        self.assertEqual(asignacion["texto"], "x = 5")
        # la funcion lista sus parametros
        funcion = next(i for i in datos["instrucciones"] if i["op"] == "func" and i["arg1"] == "f")
        self.assertEqual(funcion["arg2"], ["a"])

    def test_x02_extra_en_el_json(self):
        tac, opt = generar(OPTIMIZACION)
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "salida.opt")
            exportar_tac(opt, ruta, instrucciones_originales=len(tac))
            with open(ruta, encoding="utf-8") as f:
                datos = json.load(f)
        self.assertEqual((datos["instrucciones_originales"], datos["total_instrucciones"]), (23, 15))

    def test_x03_texto_del_json_coincide_con_listar(self):
        tac, _ = generar(FACTORIAL)
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "salida.tac")
            exportar_tac(tac, ruta)
            with open(ruta, encoding="utf-8") as f:
                textos = [i["texto"] for i in json.load(f)["instrucciones"]]
        self.assertEqual(textos, [l.strip() for l in listar(tac).split("\n")])


class PruebasMain(unittest.TestCase):
    """main.py con el TAC integrado: genera .tac y .opt, ejecuta y respeta el orden de las fases."""

    def correr_main(self, fuente, ejecutar_programa=True):
        with tempfile.TemporaryDirectory() as carpeta:
            entrada = os.path.join(carpeta, "prog.pse")
            with open(entrada, "w", encoding="utf-8") as f:
                f.write(fuente)
            base = os.path.join(carpeta, "prog")
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                codigo = compilar(entrada, base, ejecutar_programa)
            archivos = {}
            for ext in (".lex", ".syn", ".der", ".sem", ".tac", ".opt"):
                ruta = base + ext
                if os.path.exists(ruta):
                    with open(ruta, encoding="utf-8") as f:
                        archivos[ext] = json.load(f)
        return codigo, salida.getvalue(), archivos

    def test_m01_programa_valido_genera_todo_y_ejecuta(self):
        codigo, salida, archivos = self.correr_main(FACTORIAL)
        self.assertEqual(codigo, 0)
        self.assertEqual(set(archivos), {".lex", ".syn", ".der", ".sem", ".tac", ".opt"})
        self.assertTrue(archivos[".tac"]["exito"] and archivos[".opt"]["exito"])
        self.assertIn("--- Ejecución ---", salida)
        self.assertIn("Factorial: ", salida)
        self.assertIn("120", salida)

    def test_m02_sin_ejecutar_solo_genera_archivos(self):
        codigo, salida, archivos = self.correr_main(FACTORIAL, ejecutar_programa=False)
        self.assertEqual(codigo, 0)
        self.assertIn(".opt", archivos)
        self.assertNotIn("--- Ejecución ---", salida)

    def test_m03_error_lexico_omite_las_demas_fases(self):
        codigo, _, archivos = self.correr_main("x = 3.;")
        self.assertEqual(codigo, 1)
        for ext in (".syn", ".sem", ".tac", ".opt"):
            self.assertTrue(archivos[ext].get("omitido"), ext)

    def test_m04_error_sintactico_omite_semantico_y_tac(self):
        codigo, _, archivos = self.correr_main("x = 5\nescribir(x);")
        self.assertEqual(codigo, 1)
        self.assertFalse(archivos[".syn"]["exito"])
        for ext in (".sem", ".tac", ".opt"):
            self.assertTrue(archivos[ext].get("omitido"), ext)

    def test_m05_error_semantico_omite_el_tac(self):
        codigo, _, archivos = self.correr_main("escribir(y);")
        self.assertEqual(codigo, 1)
        self.assertFalse(archivos[".sem"]["exito"])
        for ext in (".tac", ".opt"):
            self.assertTrue(archivos[ext].get("omitido"), ext)

    def test_m06_error_en_ejecucion_devuelve_1(self):
        codigo, salida, archivos = self.correr_main("a = 5; b = a - 5; escribir(10 / b);")
        self.assertEqual(codigo, 1)
        self.assertIn("división entre cero", salida)
        self.assertTrue(archivos[".tac"]["exito"])  # los archivos si se generaron


if __name__ == "__main__":
    unittest.main()