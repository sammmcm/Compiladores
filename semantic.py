"""
semantic.py - Fase 3 del front-end: analisis semantico.

Recorre el AST, infiere el tipo de cada expresion, lleva una tabla de simbolos
por alcance (global y funcion) y ANOTA el arbol (tipo inferido, scope, etc.).
Acumula todos los errores en vez de detenerse en el primero.

Tipos del lenguaje: entero, decimal, cadena, booleano.
    - entero (op) entero -> entero      (excepto '/', que siempre da decimal)
    - si algun operando es decimal -> decimal
    - los operadores aritmeticos no aceptan cadenas ni booleanos
    - en una reasignacion, entero se ensancha a decimal; otros cambios de tipo son error

Alcances: un alcance global y uno por funcion. No hay declaracion explicita:
la primera asignacion crea la variable en el alcance actual. Un parametro o una
variable local con el mismo nombre que una global la oculta.

Para no generar errores en cascada, una expresion con error toma el tipo
interno "error" y los chequeos posteriores sobre ella se omiten.
"""
from errores import CompilerError
from parser import (
    Asignacion, Si, Mientras, Para, Escribir, Leer, Retornar,
    LlamadaFuncion, OperacionBinaria, OperacionUnaria, Literal,
    Identificador, FuncionDecl,
)

OPERADORES_ARITMETICOS = {"+", "-", "*", "/", "%"}
OPERADORES_RELACIONALES = {"==", "!=", "<=", ">=", "<", ">"}
NUMERICOS = {"entero", "decimal"}
TIPO_INDETERMINADO = "indeterminado"  # valor de leer(), de una llamada o de un parametro
TIPO_ERROR = "error"                  # ya se reporto un error sobre esta expresion


class Simbolo:
    def __init__(self, nombre, tipo, linea_declaracion, scope):
        self.nombre = nombre
        self.tipo = tipo
        self.linea_declaracion = linea_declaracion
        self.scope = scope
        self.usos = 0

    def to_dict(self):
        return {
            "tipo": self.tipo,
            "scope": self.scope,
            "linea_declaracion": self.linea_declaracion,
            "usos": self.usos,
        }


class Scope:
    """Tabla de simbolos de un unico alcance (global o el cuerpo de una funcion)."""

    def __init__(self, nombre: str):
        self.nombre = nombre
        self.simbolos: dict[str, Simbolo] = {}

    def resolver(self, nombre):
        simbolo = self.simbolos.get(nombre)
        if simbolo is not None:
            simbolo.usos += 1
        return simbolo

    def to_dict(self):
        return {n: s.to_dict() for n, s in self.simbolos.items()}


class AnalizadorSemantico:
    def __init__(self, programa):
        self.programa = programa
        self.errores: list[CompilerError] = []
        self.global_scope = Scope("global")
        self.funciones: dict[str, FuncionDecl] = {}
        self.tabla_funciones: dict[str, Scope] = {}

    def _error(self, mensaje, linea):
        self.errores.append(CompilerError("semantico", linea, mensaje))

    # ---------- punto de entrada ----------
    def analizar(self):
        # 1a pasada: registrar funciones (permite llamarlas antes de su definicion)
        for elemento in self.programa.elementos:
            if isinstance(elemento, FuncionDecl):
                if elemento.nombre in self.funciones:
                    primera = self.funciones[elemento.nombre].linea
                    self._error(
                        f"Función '{elemento.nombre}' ya fue declarada en la línea {primera}",
                        elemento.linea)
                    continue
                self.funciones[elemento.nombre] = elemento

        # 2a pasada: analizar cuerpos
        for elemento in self.programa.elementos:
            if isinstance(elemento, FuncionDecl):
                if self.funciones.get(elemento.nombre) is elemento:
                    self._analizar_funcion(elemento)
            else:
                self._analizar_instruccion(elemento, self.global_scope, en_funcion=False)
        return self.errores

    def _analizar_funcion(self, decl: FuncionDecl):
        scope = Scope(decl.nombre)
        for parametro in decl.parametros:
            if parametro in scope.simbolos:
                self._error(f"Parámetro '{parametro}' repetido en la función '{decl.nombre}'", decl.linea)
                continue
            scope.simbolos[parametro] = Simbolo(parametro, TIPO_INDETERMINADO, decl.linea, scope.nombre)
        self.tabla_funciones[decl.nombre] = scope
        decl.anotaciones = {"scope": decl.nombre, "total_parametros": len(decl.parametros)}
        for instruccion in decl.cuerpo:
            self._analizar_instruccion(instruccion, scope, en_funcion=True)

    # ---------- asignacion / tabla de simbolos ----------
    def _asignar(self, nombre, tipo, linea, scope: Scope) -> dict:
        """Crea la variable o valida la reasignacion. Devuelve las notas del nodo."""
        existente = scope.simbolos.get(nombre)
        if existente is None:
            scope.simbolos[nombre] = Simbolo(nombre, tipo, linea, scope.nombre)
            return {"scope": scope.nombre, "tipo_variable": tipo, "nueva_declaracion": True}

        actual = existente.tipo
        if tipo == TIPO_ERROR:
            pass
        elif actual == TIPO_ERROR:
            existente.tipo = tipo  # la variable "se recupera" con un valor valido
        elif actual == tipo:
            pass
        elif actual in NUMERICOS and tipo in NUMERICOS:
            existente.tipo = "decimal"  # ensanchamiento entero -> decimal
        elif TIPO_INDETERMINADO in (actual, tipo):
            existente.tipo = TIPO_INDETERMINADO
        else:
            self._error(
                f"No se puede asignar un valor '{tipo}' a '{nombre}', que es de tipo '{actual}'", linea)
        return {"scope": scope.nombre, "tipo_variable": existente.tipo, "nueva_declaracion": False}

    # ---------- instrucciones ----------
    def _analizar_instruccion(self, nodo, scope: Scope, en_funcion: bool):
        if isinstance(nodo, Asignacion):
            tipo = self._analizar_expresion(nodo.expresion, scope)
            nodo.anotaciones = self._asignar(nodo.identificador, tipo, nodo.linea, scope)

        elif isinstance(nodo, Si):
            self._esperar_booleano(nodo.condicion, scope, "la condición de 'si'")
            for i in nodo.bloque_si:
                self._analizar_instruccion(i, scope, en_funcion)
            for i in (nodo.bloque_sino or []):
                self._analizar_instruccion(i, scope, en_funcion)

        elif isinstance(nodo, Mientras):
            self._esperar_booleano(nodo.condicion, scope, "la condición de 'mientras'")
            for i in nodo.cuerpo:
                self._analizar_instruccion(i, scope, en_funcion)

        elif isinstance(nodo, Para):
            self._analizar_instruccion(nodo.inicializacion, scope, en_funcion)
            self._esperar_booleano(nodo.condicion, scope, "la condición de 'para'")
            self._analizar_instruccion(nodo.incremento, scope, en_funcion)
            for i in nodo.cuerpo:
                self._analizar_instruccion(i, scope, en_funcion)

        elif isinstance(nodo, Escribir):
            self._analizar_expresion(nodo.expresion, scope)

        elif isinstance(nodo, Leer):
            nodo.anotaciones = self._asignar(nodo.identificador, TIPO_INDETERMINADO, nodo.linea, scope)

        elif isinstance(nodo, Retornar):
            if not en_funcion:
                self._error("'retornar' usado fuera de una función", nodo.linea)
            self._analizar_expresion(nodo.expresion, scope)

        elif isinstance(nodo, LlamadaFuncion):
            self._analizar_expresion(nodo, scope)  # llamada como instruccion

        else:
            raise CompilerError(
                "semantico", getattr(nodo, "linea", 0),
                f"Nodo de instrucción no reconocido: {type(nodo).__name__}")

    def _esperar_booleano(self, expr, scope, contexto):
        tipo = self._analizar_expresion(expr, scope)
        if tipo not in (TIPO_INDETERMINADO, TIPO_ERROR, "booleano"):
            self._error(f"Se esperaba una expresión booleana en {contexto}, se obtuvo '{tipo}'", expr.linea)

    # ---------- expresiones ----------
    def _analizar_expresion(self, nodo, scope: Scope) -> str:
        """Infiere el tipo y lo guarda como anotacion del nodo."""
        tipo = self._tipo_expresion(nodo, scope)
        extra = getattr(nodo, "anotaciones", {})
        nodo.anotaciones = {"tipo_inferido": tipo, **extra}
        return tipo

    def _tipo_expresion(self, nodo, scope: Scope) -> str:
        if isinstance(nodo, Literal):
            return nodo.tipo_valor

        if isinstance(nodo, Identificador):
            simbolo = scope.resolver(nodo.nombre)
            if simbolo is None and scope is not self.global_scope:
                simbolo = self.global_scope.resolver(nodo.nombre)
            if simbolo is None:
                self._error(f"Variable '{nodo.nombre}' no declarada", nodo.linea)
                nodo.anotaciones = {"resuelto": False}
                return TIPO_ERROR
            nodo.anotaciones = {"scope": simbolo.scope, "declarado_en_linea": simbolo.linea_declaracion}
            return simbolo.tipo

        if isinstance(nodo, OperacionUnaria):
            tipo = self._analizar_expresion(nodo.operando, scope)
            if not self._es_numerico_o_pasa(tipo, nodo.linea, "el operador unario '-'"):
                return TIPO_ERROR
            return tipo

        if isinstance(nodo, OperacionBinaria):
            return self._tipo_binaria(nodo, scope)

        if isinstance(nodo, LlamadaFuncion):
            decl = self.funciones.get(nodo.nombre)
            for arg in nodo.argumentos:
                self._analizar_expresion(arg, scope)
            if decl is None:
                self._error(f"Función '{nodo.nombre}' no declarada", nodo.linea)
                nodo.anotaciones = {"resuelto": False}
                return TIPO_ERROR
            if len(nodo.argumentos) != len(decl.parametros):
                self._error(
                    f"'{nodo.nombre}' esperaba {len(decl.parametros)} argumento(s) "
                    f"pero recibió {len(nodo.argumentos)}", nodo.linea)
            nodo.anotaciones = {
                "funcion_declarada_en_linea": decl.linea,
                "parametros_esperados": len(decl.parametros),
            }
            return TIPO_INDETERMINADO  # el lenguaje no declara tipo de retorno

        raise CompilerError(
            "semantico", getattr(nodo, "linea", 0),
            f"Nodo de expresión no reconocido: {type(nodo).__name__}")

    def _es_numerico_o_pasa(self, tipo, linea, contexto) -> bool:
        """True si el tipo es numerico o no se puede verificar; si no, reporta error."""
        if tipo in NUMERICOS or tipo in (TIPO_INDETERMINADO, TIPO_ERROR):
            return tipo != TIPO_ERROR
        self._error(f"Se esperaba un tipo numérico en {contexto}, se obtuvo '{tipo}'", linea)
        return False

    def _tipo_binaria(self, nodo: OperacionBinaria, scope: Scope) -> str:
        izq = self._analizar_expresion(nodo.izquierda, scope)
        der = self._analizar_expresion(nodo.derecha, scope)
        op = nodo.operador

        if op in OPERADORES_ARITMETICOS:
            ok_izq = self._es_numerico_o_pasa(izq, nodo.linea, f"el operando izquierdo de '{op}'")
            ok_der = self._es_numerico_o_pasa(der, nodo.linea, f"el operando derecho de '{op}'")
            if not (ok_izq and ok_der):
                return TIPO_ERROR
            if op in ("/", "%") and isinstance(nodo.derecha, Literal) and nodo.derecha.valor == 0:
                self._error(f"División entre cero con el operador '{op}'", nodo.linea)
                return TIPO_ERROR
            if TIPO_INDETERMINADO in (izq, der):
                return TIPO_INDETERMINADO
            if op == "/" or "decimal" in (izq, der):
                return "decimal"  # coercion: la division de enteros siempre da decimal
            return "entero"

        if op in OPERADORES_RELACIONALES:
            if TIPO_ERROR in (izq, der) or TIPO_INDETERMINADO in (izq, der):
                return "booleano"
            if izq in NUMERICOS and der in NUMERICOS:
                return "booleano"
            if izq != der:
                self._error(f"Comparación '{op}' entre tipos incompatibles: '{izq}' y '{der}'", nodo.linea)
            elif izq == "booleano" and op not in ("==", "!="):
                self._error(f"Los booleanos solo se pueden comparar con '==' o '!=', no con '{op}'", nodo.linea)
            return "booleano"

        raise CompilerError("semantico", nodo.linea, f"Operador desconocido '{op}'")

    # ---------- exportacion ----------
    def tabla_simbolos_dict(self):
        return {
            "global": self.global_scope.to_dict(),
            "funciones": {
                nombre: {
                    "linea_declaracion": self.funciones[nombre].linea,
                    "parametros": self.funciones[nombre].parametros,
                    "variables_locales": scope.to_dict(),
                }
                for nombre, scope in self.tabla_funciones.items()
            },
        }


def analizar_semantica(programa):
    """Devuelve (errores, tabla_simbolos_dict). Anota el AST in situ."""
    analizador = AnalizadorSemantico(programa)
    errores = analizador.analizar()
    return errores, analizador.tabla_simbolos_dict()
