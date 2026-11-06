"""
lexer.py - Fase 1 del front-end: analisis lexico (escaner).

Convierte el codigo fuente (.pse / .txt) en una lista de tokens y reporta
TODOS los errores lexicos que encuentre (no se detiene en el primero).

Cada token guarda su tipo, su lexema (el texto tal cual), su linea y su
columna. Los espacios, los saltos de linea y los comentarios se descartan
porque no aportan a la sintaxis.

Uso independiente:
    python lexer.py entrada.pse salida.lex

Codigos de salida: 0 sin errores, 1 si falta el archivo o los argumentos,
2 si hubo errores lexicos.
"""
import json
import re
import sys
from dataclasses import dataclass, asdict
from typing import List
from errores import CompilerError


# --------------------- 1. Definicion de tokens ---------------------

# palabras reservadas del lenguaje (distinguen mayusculas de minusculas).
# se reconocen primero como IDENTIFICADOR y luego se compara el lexema con este conjunto.
PALABRAS_CLAVE = {
    "si", "sino", "mientras", "para", "funcion", "retornar",
    "leer", "escribir", "verdadero", "falso",
}

# (nombre del token, expresion regular). 
# El orden importa: Python prueba las alternativas en secuencia y se queda con la
# primera que coincide (no con la mas larga), asi que lo mas especifico va primero. 
# Por ejemplo:
#   - COMENTARIO antes que OP_ARITMETICO, para que '//' no sean dos divisiones
#   - OP_REL antes que OP_ASIGNACION y '==' / '<=' antes que '<' / '>',
#     para que no se partan en dos tokens
#   - DESCONOCIDO al final, para que solo atrape lo que nada mas reconocio
ESPECIFICACION_TOKENS = [
    ("COMENTARIO",        r"//[^\n]*"),                 # se descarta
    ("ESPACIO",           r"[ \t\r]+"),                 # se descarta
    ("SALTO_LINEA",       r"\n"),                       # solo sirve para contar lineas
    ("CANDIDATO_NUMERO",  r"\d(?:[\w.]|(?<=[eE])[+-])*"),
    # todo lo que parece numero (empieza con digito), despues se valida con _NUMERO_VALIDO: asi detectamos 3., 1.2.3, 2e, 5abc, etc. como mal formados.
    ("CADENA",            r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\''),   # "texto" o 'texto', con escapes
    ("CADENA_SIN_CERRAR", r'"(?:[^"\\\n]|\\.)*|\'(?:[^\'\\\n]|\\.)*'),      # comilla abierta sin cierre en la linea
    ("IDENTIFICADOR",     r"[A-Za-z_][A-Za-z0-9_]*"),   # tambien atrapa las palabras clave
    ("OP_REL",            r"==|!=|<=|>=|<|>"),
    ("OP_ASIGNACION",     r"="),
    ("OP_ARITMETICO",     r"\+|-|\*|/|%"),
    ("PARENTESIS_IZQ",    r"\("),
    ("PARENTESIS_DER",    r"\)"),
    ("LLAVE_IZQ",         r"\{"),
    ("LLAVE_DER",         r"\}"),
    ("COMA",              r","),
    ("PUNTOCOMA",         r";"),
    ("DESCONOCIDO",       r"."),  # cualquier otro caracter -> error lexico
]

# patron maestro: une todas las reglas en una sola expresion, cada una como
# grupo con nombre (?P<NOMBRE>...). El nombre del grupo que coincide
# (match.lastgroup) es el tipo del token.
_PATRON_MAESTRO = re.compile(
    "|".join(f"(?P<{nombre}>{patron})" for nombre, patron in ESPECIFICACION_TOKENS)
)

# numero valido: entero, decimal o notacion cientifica (12, 3.14, 1.5e-3, 2E10)
_NUMERO_VALIDO = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")


# --------------------- 2. Estructuras de datos ---------------------
@dataclass
class Token:
    """Un token del codigo fuente."""
    tipo: str      # por ejemplo "NUMERO", "IDENTIFICADOR", "PALABRA_CLAVE"
    lexema: str    # el texto tal cual aparece en el codigo
    linea: int     # linea donde empieza (desde 1)
    columna: int   # columna donde empieza (desde 1, un tabulador cuenta como 1)


# --------------------- 3. Analizador lexico ---------------------
class AnalizadorLexico:
    """Escaner: recorre el codigo fuente y llena `tokens` y `errores`.

    Uso:
        analizador = AnalizadorLexico(codigo)
        analizador.analizar()
        analizador.tokens    # lista de Token validos
        analizador.errores   # lista de CompilerError (fase "lexico")
    """

    def __init__(self, codigo_fuente: str):
        self.codigo_fuente = codigo_fuente
        self.tokens: List[Token] = []
        self.errores: List[CompilerError] = []

    def _error(self, mensaje: str, linea: int, columna: int) -> None:
        """Registra un error lexico. No detiene el analisis."""
        self.errores.append(CompilerError("lexico", linea, mensaje, columna))

    def analizar(self) -> None:
        """Recorre todo el codigo fuente generando tokens.

        En cada vuelta intenta un match con el patron maestro desde la
        posicion actual. Despues de un error se sigue, para reportar todos:
        un caracter desconocido se salta de uno en uno, un numero mal formado
        se descarta completo y una cadena sin cerrar descarta el resto de su linea.
        """
        linea = 1
        inicio_linea = 0  # indice donde comienza la linea actual (para la columna)
        pos = 0
        longitud = len(self.codigo_fuente)

        while pos < longitud:
            match = _PATRON_MAESTRO.match(self.codigo_fuente, pos)
            tipo = match.lastgroup
            lexema = match.group()
            columna = match.start() - inicio_linea + 1
            pos = match.end()

            if tipo == "SALTO_LINEA":
                linea += 1
                inicio_linea = pos
                continue

            if tipo in ("ESPACIO", "COMENTARIO"):
                continue  # no aportan a la sintaxis

            if tipo == "CANDIDATO_NUMERO":
                if _NUMERO_VALIDO.fullmatch(lexema):
                    tipo = "NUMERO"
                else:
                    self._error(f"Número mal formado: '{lexema}'", linea, columna)
                    continue

            elif tipo == "IDENTIFICADOR" and lexema in PALABRAS_CLAVE:
                tipo = "PALABRA_CLAVE"

            elif tipo == "CADENA_SIN_CERRAR":
                self._error(f"Cadena sin cerrar: {lexema}", linea, columna)
                # nada de lo que quede en la linea puede ser un token valido
                fin_linea = self.codigo_fuente.find("\n", pos)
                pos = fin_linea if fin_linea != -1 else longitud
                continue

            elif tipo == "DESCONOCIDO":
                self._error(f"Carácter no reconocido: '{lexema}'", linea, columna)
                continue  # seguimos para reportar todos los errores

            self.tokens.append(Token(tipo, lexema, linea, columna))

    def exportar_json(self, ruta_salida: str) -> None:
        """Guarda el resultado en un archivo .lex (JSON) con los campos
        exito, total_tokens, tokens y errores."""
        resultado = {
            "exito": not self.errores,
            "total_tokens": len(self.tokens),
            "tokens": [asdict(t) for t in self.tokens],
            "errores": [e.to_dict() for e in self.errores],
        }
        with open(ruta_salida, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)


# --------------------- 4. Punto de entrada (uso independiente) ---------------------
def main() -> None:
    """Corre solo el escaner: lee un archivo, lo analiza y escribe el .lex."""
    if len(sys.argv) != 3:
        print("Uso: python lexer.py <entrada.pse|.txt> <salida.lex>")
        sys.exit(1)

    ruta_entrada, ruta_salida = sys.argv[1], sys.argv[2]
    try:
        with open(ruta_entrada, "r", encoding="utf-8") as f:
            codigo = f.read()
    except OSError as e:
        print(f"Error al leer el archivo de entrada: {e}")
        sys.exit(1)

    analizador = AnalizadorLexico(codigo)
    analizador.analizar()
    analizador.exportar_json(ruta_salida)

    if analizador.errores:
        print(f"Análisis léxico con {len(analizador.errores)} error(es). Ver {ruta_salida}")
        sys.exit(2)
    print(f"Análisis léxico correcto: {len(analizador.tokens)} tokens en {ruta_salida}")


if __name__ == "__main__":
    main()
