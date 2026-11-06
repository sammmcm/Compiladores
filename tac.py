"""
tac.py - Fase 4 (Entregable 1)

Recibe el AST ya anotado por semantic.py y genera una lista de cuadruplos
(op, arg1, arg2, resultado). Incluye un optimizador local preliminar
(plegado y propagacion de constantes, codigo muerto) y un interprete
para ejecutar el TAC y comprobar que el resultado es correcto.

Uso:
    python tac.py entrada.pse            (muestra TAC original, optimizado y la ejecucion)
"""
import sys
from dataclasses import dataclass

from parser import (
    Asignacion, Si, Mientras, Para, Escribir, Leer, Retornar,
    LlamadaFuncion, OperacionBinaria, OperacionUnaria, Literal,
    Identificador, FuncionDecl,
)

BINARIOS = {"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">="}


# --------------------- Cuadruplo ---------------------
@dataclass
class Cuadruplo:
    op: str            # ver tabla de instrucciones en la documentacion
    arg1: object = None
    arg2: object = None
    res: object = None

    def __str__(self):
        a1, a2, r = (_fmt(x) for x in (self.arg1, self.arg2, self.res))
        op = self.op
        if op in BINARIOS:
            return f"    {r} = {a1} {op} {a2}"
        if op == "uminus":
            return f"    {r} = - {a1}"
        if op == "=":
            return f"    {r} = {a1}"
        if op == "label":
            return f"{r}:"
        if op == "goto":
            return f"    goto {r}"
        if op == "if_false":
            return f"    if_false {a1} goto {r}"
        if op == "param":
            return f"    param {a1}"
        if op == "call":
            return f"    {r} = call {a1}, {a2}" if self.res else f"    call {a1}, {a2}"
        if op == "return":
            return f"    return {a1}"
        if op == "read":
            return f"    read {r}"
        if op == "write":
            return f"    write {a1}"
        if op == "func":
            return f"func {a1}({', '.join(self.arg2)}):"
        if op == "endfunc":
            return f"endfunc"
        return f"    {op} {a1} {a2} {r}"


@dataclass(frozen=True)
class Const:
    """Operando constante (para distinguirlo de un nombre de variable)."""
    valor: object


def _fmt(x):
    if x is None:
        return ""
    if isinstance(x, Const):
        v = x.valor
        if isinstance(v, bool):
            return "verdadero" if v else "falso"
        if isinstance(v, str):
            return '"' + v + '"'
        return repr(v)
    return str(x)


# --------------------- Generador ---------------------
class GeneradorTAC:
    def __init__(self):
        self.codigo: list[Cuadruplo] = []
        self.n_temp = 0
        self.n_etiqueta = 0

    def temp(self):
        self.n_temp += 1
        return f"t{self.n_temp}"

    def etiqueta(self):
        self.n_etiqueta += 1
        return f"L{self.n_etiqueta}"

    def emitir(self, *args):
        self.codigo.append(Cuadruplo(*args))

    def generar(self, programa):
        funciones = [e for e in programa.elementos if isinstance(e, FuncionDecl)]
        principal = [e for e in programa.elementos if not isinstance(e, FuncionDecl)]
        self.emitir("func", "main", [])
        for i in principal:
            self.instruccion(i)
        self.emitir("endfunc")
        for f in funciones:
            self.emitir("func", f.nombre, list(f.parametros))
            for i in f.cuerpo:
                self.instruccion(i)
            self.emitir("return", Const(0))  # retorno implicito si el cuerpo no retorna
            self.emitir("endfunc")
        return self.codigo

    # ---------- instrucciones ----------
    def instruccion(self, n):
        if isinstance(n, Asignacion):
            self.emitir("=", self.expr(n.expresion), None, n.identificador)
        elif isinstance(n, Escribir):
            self.emitir("write", self.expr(n.expresion))
        elif isinstance(n, Leer):
            self.emitir("read", None, None, n.identificador)
        elif isinstance(n, Retornar):
            self.emitir("return", self.expr(n.expresion))
        elif isinstance(n, LlamadaFuncion):
            self.llamada(n, con_resultado=False)
        elif isinstance(n, Si):
            l_sino = self.etiqueta() if n.bloque_sino else None
            l_fin = self.etiqueta()
            self.emitir("if_false", self.expr(n.condicion), None, l_sino if n.bloque_sino else l_fin)
            for i in n.bloque_si:
                self.instruccion(i)
            if n.bloque_sino:
                self.emitir("goto", None, None, l_fin)
                self.emitir("label", None, None, l_sino)
                for i in n.bloque_sino:
                    self.instruccion(i)
            self.emitir("label", None, None, l_fin)
        elif isinstance(n, Mientras):
            l_cond, l_fin = self.etiqueta(), self.etiqueta()
            self.emitir("label", None, None, l_cond)
            self.emitir("if_false", self.expr(n.condicion), None, l_fin)
            for i in n.cuerpo:
                self.instruccion(i)
            self.emitir("goto", None, None, l_cond)
            self.emitir("label", None, None, l_fin)
        elif isinstance(n, Para):
            l_cond, l_fin = self.etiqueta(), self.etiqueta()
            self.instruccion(n.inicializacion)
            self.emitir("label", None, None, l_cond)
            self.emitir("if_false", self.expr(n.condicion), None, l_fin)
            for i in n.cuerpo:
                self.instruccion(i)
            self.instruccion(n.incremento)
            self.emitir("goto", None, None, l_cond)
            self.emitir("label", None, None, l_fin)
        else:
            raise ValueError(f"Nodo no soportado: {type(n).__name__}")

    # ---------- expresiones: devuelven el operando que guarda el valor ----------
    def expr(self, n):
        if isinstance(n, Literal):
            return Const(n.valor)
        if isinstance(n, Identificador):
            return n.nombre
        if isinstance(n, OperacionUnaria):
            a = self.expr(n.operando)
            t = self.temp()
            self.emitir("uminus", a, None, t)
            return t
        if isinstance(n, OperacionBinaria):
            a = self.expr(n.izquierda)
            b = self.expr(n.derecha)
            t = self.temp()
            self.emitir(n.operador, a, b, t)
            return t
        if isinstance(n, LlamadaFuncion):
            return self.llamada(n, con_resultado=True)
        raise ValueError(f"Expresion no soportada: {type(n).__name__}")

    def llamada(self, n, con_resultado):
        args = [self.expr(a) for a in n.argumentos]  # primero se evaluan todos
        for a in args:
            self.emitir("param", a)
        t = self.temp() if con_resultado else None
        self.emitir("call", n.nombre, len(args), t)
        return t


# --------------------- Operaciones (compartidas por optimizador e interprete) ---------------------
def aplicar(op, a, b):
    if op == "+": return a + b
    if op == "-": return a - b
    if op == "*": return a * b
    if op == "/": return a / b          # siempre decimal (regla del analisis semantico)
    if op == "%": return a % b
    if op == "==": return a == b
    if op == "!=": return a != b
    if op == "<": return a < b
    if op == "<=": return a <= b
    if op == ">": return a > b
    if op == ">=": return a >= b
    raise ValueError(op)


# --------------------- Optimizador (preliminar) ---------------------
def optimizar(codigo):
    """Pasadas hasta punto fijo: plegado + propagacion de constantes (local al bloque
    basico), salto con condicion constante, codigo inalcanzable y temporales sin uso."""
    codigo = list(codigo)
    while True:
        nuevo = _eliminar_temporales_muertos(_eliminar_inalcanzable(_constantes(codigo)))
        if [str(c) for c in nuevo] == [str(c) for c in codigo]:
            return nuevo
        codigo = nuevo


def _constantes(codigo):
    salida = []
    valores = {}  # nombre -> Const conocido dentro del bloque basico
    val = lambda x: valores.get(x, x) if isinstance(x, str) else x
    for c in codigo:
        # al iniciar un bloque basico se olvida lo conocido
        if c.op in ("label", "func"):
            valores.clear()
            salida.append(c)
            continue
        a1, a2 = val(c.arg1), val(c.arg2)
        if c.op in BINARIOS and isinstance(a1, Const) and isinstance(a2, Const):
            if not (c.op in ("/", "%") and a2.valor == 0):  # la division entre cero no se pliega
                valores[c.res] = Const(aplicar(c.op, a1.valor, a2.valor))
                salida.append(Cuadruplo("=", valores[c.res], None, c.res))
                continue
        if c.op == "uminus" and isinstance(a1, Const):
            valores[c.res] = Const(-a1.valor)
            salida.append(Cuadruplo("=", valores[c.res], None, c.res))
            continue
        if c.op == "if_false" and isinstance(a1, Const):
            if not a1.valor:
                salida.append(Cuadruplo("goto", None, None, c.res))
            continue  # condicion siempre verdadera: el salto desaparece
        nuevo = Cuadruplo(c.op, a1 if c.op != "call" else c.arg1, a2, c.res)
        if c.op == "func":
            nuevo = c
        salida.append(nuevo)
        # actualizar lo conocido
        if c.op == "=":
            if isinstance(a1, Const):
                valores[c.res] = a1
            else:
                valores.pop(c.res, None)
        elif c.op in ("read",) or (c.op in BINARIOS | {"uminus", "call"} and c.res):
            valores.pop(c.res, None)
        if c.op == "call":
            valores.clear()
        if c.op in ("goto", "if_false", "return"):
            valores.clear()
    return salida


def _eliminar_inalcanzable(codigo):
    """Quita lo que sigue a un goto/return hasta la siguiente etiqueta, los saltos
    a la etiqueta inmediata siguiente y las etiquetas que nadie usa."""
    salida, muerto = [], False
    for c in codigo:
        if c.op in ("label", "func", "endfunc"):
            muerto = False
        if muerto:
            continue
        salida.append(c)
        if c.op in ("goto", "return"):
            muerto = True
    limpio = []
    for i, c in enumerate(salida):
        if c.op == "goto" and i + 1 < len(salida) and salida[i + 1].op == "label" and salida[i + 1].res == c.res:
            continue
        limpio.append(c)
    usadas = {c.res for c in limpio if c.op in ("goto", "if_false")}
    return [c for c in limpio if c.op != "label" or c.res in usadas]


def _eliminar_temporales_muertos(codigo):
    usados = set()
    for c in codigo:
        for a in (c.arg1, c.arg2):
            if isinstance(a, str):
                usados.add(a)
    return [c for c in codigo
            if not (c.op in BINARIOS | {"=", "uminus"} and isinstance(c.res, str)
                    and c.res.startswith("t") and c.res[1:].isdigit() and c.res not in usados)]


# --------------------- Interprete ----------------------------
def ejecutar(codigo, entrada=None, salida=print):
    entrada = list(entrada or [])
    funcs, etiquetas = {}, {}
    for i, c in enumerate(codigo):
        if c.op == "func":
            funcs[c.arg1] = i
        elif c.op == "label":
            etiquetas[c.res] = i
    globales = {}

    def correr(nombre, args):
        pc = funcs[nombre] + 1
        local = dict(zip(codigo[funcs[nombre]].arg2, args))
        entorno = globales if nombre == "main" else local
        val = lambda x: x.valor if isinstance(x, Const) else (entorno[x] if x in entorno else globales[x])
        params = []
        while True:
            c = codigo[pc]
            pc += 1
            op = c.op
            if op in BINARIOS:
                entorno[c.res] = aplicar(op, val(c.arg1), val(c.arg2))
            elif op == "uminus":
                entorno[c.res] = -val(c.arg1)
            elif op == "=":
                entorno[c.res] = val(c.arg1)
            elif op == "goto":
                pc = etiquetas[c.res]
            elif op == "if_false":
                if not val(c.arg1):
                    pc = etiquetas[c.res]
            elif op == "param":
                params.append(val(c.arg1))
            elif op == "call":
                n = c.arg2
                args, params[:] = params[len(params) - n:], params[:len(params) - n]
                r = correr(c.arg1, args)
                if c.res:
                    entorno[c.res] = r
            elif op == "return":
                return val(c.arg1)
            elif op == "read":
                entorno[c.res] = entrada.pop(0)
            elif op == "write":
                v = val(c.arg1)
                salida(("verdadero" if v else "falso") if isinstance(v, bool) else v)
            elif op == "endfunc":
                return 0

    correr("main", [])


def listar(codigo):
    return "\n".join(str(c) for c in codigo)


if __name__ == "__main__":
    from lexer import AnalizadorLexico
    from parser import parsear_tokens
    from semantic import analizar_semantica

    fuente = open(sys.argv[1], encoding="utf-8").read()
    lx = AnalizadorLexico(fuente)
    lx.analizar()
    ast, err_sin = parsear_tokens(lx.tokens)
    err_sem, _ = analizar_semantica(ast)
    if lx.errores or err_sin or err_sem:
        for e in lx.errores + err_sin + err_sem:
            print(e)
        sys.exit(2)
    tac = GeneradorTAC().generar(ast)
    opt = optimizar(tac)
    print(f"--- TAC original ({len(tac)} instrucciones) ---\n{listar(tac)}")
    print(f"\n--- TAC optimizado ({len(opt)} instrucciones) ---\n{listar(opt)}")
    print("\n--- Ejecucion ---")
    ejecutar(opt)
