"""
parser.py - Fase 2 del front-end: analisis sintactico (descenso recursivo).

Recibe los tokens del lexer y construye el AST (arbol sintactico abstracto).
Si encuentra un error lo registra, descarta tokens hasta un punto seguro y sigue,
para poder reportar varios errores sintacticos.

El lexer no emite EOF, asi que se agrega uno sintetico en `parsear_tokens`.
"""
from dataclasses import dataclass

from lexer import Token
from errores import CompilerError

# palabras con las que puede empezar una instruccion
INICIO_INSTRUCCION = {"si", "mientras", "para", "funcion", "retornar", "leer", "escribir"}

NOMBRES_TOKEN = {
    "PUNTOCOMA": "';'", "PARENTESIS_IZQ": "'('", "PARENTESIS_DER": "')'",
    "LLAVE_IZQ": "'{'", "LLAVE_DER": "'}'", "COMA": "','",
    "OP_ASIGNACION": "'='", "IDENTIFICADOR": "un identificador",
}


# --------------------- Nodos del AST ---------------------
class Nodo:
    """Base de todos los nodos. El analisis semantico agrega `anotaciones` (tipo inferido, scope, etc.) y to_dict() las incluye al exportar."""

    def _dict(self) -> dict:
        raise NotImplementedError

    def to_dict(self) -> dict:
        d = self._dict()
        notas = getattr(self, "anotaciones", None)
        if notas:
            d["anotaciones"] = notas
        return d


@dataclass
class Programa(Nodo):
    elementos: list  # FuncionDecl o instrucciones sueltas

    def _dict(self):
        return {"tipo": "Programa", "elementos": [e.to_dict() for e in self.elementos]}


@dataclass
class FuncionDecl(Nodo):
    nombre: str
    parametros: list
    cuerpo: list
    linea: int

    def _dict(self):
        return {
            "tipo": "FuncionDecl", "nombre": self.nombre, "parametros": self.parametros,
            "cuerpo": [i.to_dict() for i in self.cuerpo], "linea": self.linea,
        }


@dataclass
class Asignacion(Nodo):
    identificador: str
    expresion: Nodo
    linea: int

    def _dict(self):
        return {
            "tipo": "Asignacion", "identificador": self.identificador,
            "expresion": self.expresion.to_dict(), "linea": self.linea,
        }


@dataclass
class Si(Nodo):
    condicion: Nodo
    bloque_si: list
    bloque_sino: list
    linea: int

    def _dict(self):
        return {
            "tipo": "Si", "condicion": self.condicion.to_dict(),
            "bloque_si": [i.to_dict() for i in self.bloque_si],
            "bloque_sino": [i.to_dict() for i in self.bloque_sino] if self.bloque_sino else None,
            "linea": self.linea,
        }


@dataclass
class Mientras(Nodo):
    condicion: Nodo
    cuerpo: list
    linea: int

    def _dict(self):
        return {
            "tipo": "Mientras", "condicion": self.condicion.to_dict(),
            "cuerpo": [i.to_dict() for i in self.cuerpo], "linea": self.linea,
        }


@dataclass
class Para(Nodo):
    inicializacion: Nodo
    condicion: Nodo
    incremento: Nodo
    cuerpo: list
    linea: int

    def _dict(self):
        return {
            "tipo": "Para", "inicializacion": self.inicializacion.to_dict(),
            "condicion": self.condicion.to_dict(), "incremento": self.incremento.to_dict(),
            "cuerpo": [i.to_dict() for i in self.cuerpo], "linea": self.linea,
        }


@dataclass
class Escribir(Nodo):
    expresion: Nodo
    linea: int

    def _dict(self):
        return {"tipo": "Escribir", "expresion": self.expresion.to_dict(), "linea": self.linea}


@dataclass
class Leer(Nodo):
    identificador: str
    linea: int

    def _dict(self):
        return {"tipo": "Leer", "identificador": self.identificador, "linea": self.linea}


@dataclass
class Retornar(Nodo):
    expresion: Nodo
    linea: int

    def _dict(self):
        return {"tipo": "Retornar", "expresion": self.expresion.to_dict(), "linea": self.linea}


@dataclass
class LlamadaFuncion(Nodo):
    nombre: str
    argumentos: list
    linea: int

    def _dict(self):
        return {
            "tipo": "LlamadaFuncion", "nombre": self.nombre,
            "argumentos": [a.to_dict() for a in self.argumentos], "linea": self.linea,
        }


@dataclass
class OperacionBinaria(Nodo):
    operador: str
    izquierda: Nodo
    derecha: Nodo
    linea: int

    def _dict(self):
        return {
            "tipo": "OperacionBinaria", "operador": self.operador,
            "izquierda": self.izquierda.to_dict(), "derecha": self.derecha.to_dict(),
            "linea": self.linea,
        }


@dataclass
class OperacionUnaria(Nodo):
    operador: str  # solo '-'
    operando: Nodo
    linea: int

    def _dict(self):
        return {
            "tipo": "OperacionUnaria", "operador": self.operador,
            "operando": self.operando.to_dict(), "linea": self.linea,
        }


@dataclass
class Literal(Nodo):
    tipo_valor: str  # entero | decimal | cadena | booleano
    valor: object
    linea: int

    def _dict(self):
        return {"tipo": "Literal", "tipo_valor": self.tipo_valor, "valor": self.valor, "linea": self.linea}


@dataclass
class Identificador(Nodo):
    nombre: str
    linea: int

    def _dict(self):
        return {"tipo": "Identificador", "nombre": self.nombre, "linea": self.linea}


# --------------------- Parser ---------------------
class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
        self.errores: list[CompilerError] = []

    # ---------- utilidades ----------
    @property
    def actual(self) -> Token:
        return self.tokens[self.pos]

    def avanzar(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def es_tipo(self, *tipos) -> bool:
        return self.actual.tipo in tipos

    def es_palabra(self, *lexemas) -> bool:
        return self.actual.tipo == "PALABRA_CLAVE" and self.actual.lexema in lexemas

    @staticmethod
    def _describir(tok: Token) -> str:
        return "el fin del archivo" if tok.tipo == "EOF" else f"'{tok.lexema}'"

    def _error(self, mensaje: str, tok: Token | None = None) -> CompilerError:
        tok = tok or self.actual
        return CompilerError("sintactico", tok.linea, mensaje, tok.columna)

    def esperar_tipo(self, tipo: str) -> Token:
        if self.actual.tipo == tipo:
            return self.avanzar()
        tok = self.actual
        linea, columna = tok.linea, tok.columna
        # un ';' que falta se reporta donde termina la ultima instruccion, no al inicio de la siguiente linea.
        if tipo == "PUNTOCOMA" and self.pos > 0:
            previo = self.tokens[self.pos - 1]
            if previo.linea < tok.linea or tok.tipo == "EOF":
                raise CompilerError(
                    "sintactico", previo.linea,
                    "Falta ';' al final de la instrucción",
                    previo.columna + len(previo.lexema),
                )
        esperado = NOMBRES_TOKEN.get(tipo, tipo)
        raise CompilerError(
            "sintactico", linea,
            f"Se esperaba {esperado} pero se encontró {self._describir(tok)}", columna,
        )

    # ---------- recuperacion de errores ----------
    def _con_recuperacion(self, regla):
        """Ejecuta una regla; si falla, registra el error y sincroniza."""
        inicio = self.pos
        try:
            return regla()
        except CompilerError as err:
            self.errores.append(err)
            self._sincronizar(inicio)
            return None

    def _sincronizar(self, inicio: int) -> None:
        """Descarta tokens hasta un punto seguro: despues de ';', antes de '}' o de una palabra que inicia
        instruccion. Siempre avanza al menos 1 token para garantizar que el parser no se cicle."""
        if self.pos == inicio and not self.es_tipo("EOF"):
            self.avanzar()
        while not self.es_tipo("EOF"):
            if self.tokens[self.pos - 1].tipo == "PUNTOCOMA":
                return
            if self.es_tipo("LLAVE_DER") or self.es_palabra(*INICIO_INSTRUCCION):
                return
            if self.es_tipo("LLAVE_IZQ"):
                self._saltar_bloque()  # el encabezado fallo: se omite su cuerpo completo
                return
            self.avanzar()

    def _saltar_bloque(self) -> None:
        profundidad = 0
        while not self.es_tipo("EOF"):
            tipo = self.avanzar().tipo
            if tipo == "LLAVE_IZQ":
                profundidad += 1
            elif tipo == "LLAVE_DER":
                profundidad -= 1
                if profundidad == 0:
                    return

    # ---------- programa ----------
    def parsear(self) -> Programa:
        elementos = []
        while not self.es_tipo("EOF"):
            nodo = self._con_recuperacion(self._elemento)
            if nodo is not None:
                elementos.append(nodo)
        return Programa(elementos)

    def _elemento(self):
        return self.funcion_decl() if self.es_palabra("funcion") else self.instruccion()

    def funcion_decl(self):
        linea = self.avanzar().linea  # "funcion"
        nombre = self.esperar_tipo("IDENTIFICADOR").lexema
        self.esperar_tipo("PARENTESIS_IZQ")
        parametros = []
        if not self.es_tipo("PARENTESIS_DER"):
            parametros.append(self.esperar_tipo("IDENTIFICADOR").lexema)
            while self.es_tipo("COMA"):
                self.avanzar()
                parametros.append(self.esperar_tipo("IDENTIFICADOR").lexema)
        self.esperar_tipo("PARENTESIS_DER")
        cuerpo = self.bloque()
        return FuncionDecl(nombre, parametros, cuerpo, linea)

    # ---------- instrucciones ----------
    def instruccion(self):
        if self.es_palabra("si"):
            return self.sentencia_si()
        if self.es_palabra("mientras"):
            return self.sentencia_mientras()
        if self.es_palabra("para"):
            return self.sentencia_para()
        if self.es_palabra("escribir"):
            return self.sentencia_escribir()
        if self.es_palabra("leer"):
            return self.sentencia_leer()
        if self.es_palabra("retornar"):
            return self.sentencia_retornar()
        if self.es_tipo("IDENTIFICADOR"):
            return self.asignacion_o_llamada()
        raise self._error(f"Instrucción inválida, token inesperado {self._describir(self.actual)}")

    def asignacion_o_llamada(self):
        """IDENTIFICADOR '=' expresion ';' | llamada ';'"""
        inicio = self.actual
        if self.tokens[self.pos + 1].tipo == "OP_ASIGNACION":
            self.avanzar()  # IDENTIFICADOR
            self.avanzar()  # '='
            expr = self.expresion()
            self.esperar_tipo("PUNTOCOMA")
            return Asignacion(inicio.lexema, expr, inicio.linea)
        expr = self.expresion()
        if not isinstance(expr, LlamadaFuncion):
            raise self._error("Instrucción sin efecto: se esperaba una asignación o una llamada a función", inicio)
        self.esperar_tipo("PUNTOCOMA")
        return expr

    def sentencia_si(self):
        linea = self.avanzar().linea
        self.esperar_tipo("PARENTESIS_IZQ")
        condicion = self.expresion()
        self.esperar_tipo("PARENTESIS_DER")
        bloque_si = self.bloque()
        bloque_sino = []
        if self.es_palabra("sino"):
            self.avanzar()
            bloque_sino = self.bloque()
        return Si(condicion, bloque_si, bloque_sino, linea)

    def sentencia_mientras(self):
        linea = self.avanzar().linea
        self.esperar_tipo("PARENTESIS_IZQ")
        condicion = self.expresion()
        self.esperar_tipo("PARENTESIS_DER")
        cuerpo = self.bloque()
        return Mientras(condicion, cuerpo, linea)

    def sentencia_para(self):
        linea = self.avanzar().linea
        self.esperar_tipo("PARENTESIS_IZQ")
        inicializacion = self._asignacion_sin_punto_y_coma()
        self.esperar_tipo("PUNTOCOMA")
        condicion = self.expresion()
        self.esperar_tipo("PUNTOCOMA")
        incremento = self._asignacion_sin_punto_y_coma()
        self.esperar_tipo("PARENTESIS_DER")
        cuerpo = self.bloque()
        return Para(inicializacion, condicion, incremento, cuerpo, linea)

    def _asignacion_sin_punto_y_coma(self):
        linea = self.actual.linea
        nombre = self.esperar_tipo("IDENTIFICADOR").lexema
        self.esperar_tipo("OP_ASIGNACION")
        return Asignacion(nombre, self.expresion(), linea)

    def sentencia_escribir(self):
        linea = self.avanzar().linea
        self.esperar_tipo("PARENTESIS_IZQ")
        expr = self.expresion()
        self.esperar_tipo("PARENTESIS_DER")
        self.esperar_tipo("PUNTOCOMA")
        return Escribir(expr, linea)

    def sentencia_leer(self):
        linea = self.avanzar().linea
        self.esperar_tipo("PARENTESIS_IZQ")
        nombre = self.esperar_tipo("IDENTIFICADOR").lexema
        self.esperar_tipo("PARENTESIS_DER")
        self.esperar_tipo("PUNTOCOMA")
        return Leer(nombre, linea)

    def sentencia_retornar(self):
        linea = self.avanzar().linea
        expr = self.expresion()
        self.esperar_tipo("PUNTOCOMA")
        return Retornar(expr, linea)

    def bloque(self):
        llave = self.esperar_tipo("LLAVE_IZQ")
        instrucciones = []
        while not self.es_tipo("LLAVE_DER"):
            if self.es_tipo("EOF"):
                raise self._error(
                    f"Bloque sin cerrar: la '{{' de la línea {llave.linea} no tiene su '}}'", llave)
            nodo = self._con_recuperacion(self.instruccion)
            if nodo is not None:
                instrucciones.append(nodo)
        self.avanzar()  # '}'
        return instrucciones

    # ---------- expresiones (de menor a mayor precedencia) ----------
    # comparacion  <  suma/resta  <  multiplicacion/division/modulo  <  unario  <  llamada
    def expresion(self):
        return self.comparacion()

    def comparacion(self):
        nodo = self.suma()
        while self.es_tipo("OP_REL"):
            op = self.avanzar()
            nodo = OperacionBinaria(op.lexema, nodo, self.suma(), op.linea)
        return nodo

    def suma(self):
        nodo = self.termino()
        while self.es_tipo("OP_ARITMETICO") and self.actual.lexema in ("+", "-"):
            op = self.avanzar()
            nodo = OperacionBinaria(op.lexema, nodo, self.termino(), op.linea)
        return nodo

    def termino(self):
        nodo = self.unario()
        while self.es_tipo("OP_ARITMETICO") and self.actual.lexema in ("*", "/", "%"):
            op = self.avanzar()
            nodo = OperacionBinaria(op.lexema, nodo, self.unario(), op.linea)
        return nodo

    def unario(self):
        if self.es_tipo("OP_ARITMETICO") and self.actual.lexema == "-":
            op = self.avanzar()
            return OperacionUnaria("-", self.unario(), op.linea)
        return self.llamada()

    def llamada(self):
        nodo = self.primario()
        while self.es_tipo("PARENTESIS_IZQ"):
            if not isinstance(nodo, Identificador):
                raise self._error("Solo un identificador puede invocarse como función")
            self.avanzar()
            argumentos = []
            if not self.es_tipo("PARENTESIS_DER"):
                argumentos.append(self.expresion())
                while self.es_tipo("COMA"):
                    self.avanzar()
                    argumentos.append(self.expresion())
            self.esperar_tipo("PARENTESIS_DER")
            nodo = LlamadaFuncion(nodo.nombre, argumentos, nodo.linea)
        return nodo

    def primario(self):
        tok = self.actual
        if tok.tipo == "NUMERO":
            self.avanzar()
            if any(c in tok.lexema for c in ".eE"):
                return Literal("decimal", float(tok.lexema), tok.linea)
            return Literal("entero", int(tok.lexema), tok.linea)
        if tok.tipo == "CADENA":
            self.avanzar()
            return Literal("cadena", tok.lexema[1:-1], tok.linea)
        if tok.tipo == "PALABRA_CLAVE" and tok.lexema in ("verdadero", "falso"):
            self.avanzar()
            return Literal("booleano", tok.lexema == "verdadero", tok.linea)
        if tok.tipo == "IDENTIFICADOR":
            self.avanzar()
            return Identificador(tok.lexema, tok.linea)
        if tok.tipo == "PARENTESIS_IZQ":
            self.avanzar()
            nodo = self.expresion()
            self.esperar_tipo("PARENTESIS_DER")
            return nodo
        raise self._error(
            f"Falta un operando: se esperaba un número, identificador, cadena o '(' "
            f"pero se encontró {self._describir(tok)}")


def parsear_tokens(tokens: list[Token]) -> tuple[Programa, list[CompilerError]]:
    """Agrega un EOF sintetico y parsea. Devuelve (ast, errores_sintacticos)."""
    ultima_linea = tokens[-1].linea if tokens else 1
    parser = Parser(tokens + [Token("EOF", "", ultima_linea, 1)])
    ast = parser.parsear()
    return ast, parser.errores
