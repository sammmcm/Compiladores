"""
errores.py - Error de compilacion compartido por todas las fases del front-end.

Todas las fases (lexico, sintactico y semantico) reportan sus errores con la
misma estructura, para que main.py los pueda mostrar y exportar igual sin
importar de que fase vengan. Por eso vive en su propio archivo y ninguna fase
depende de otra solo para poder reportar un error.
"""


class CompilerError(Exception):
    """Un error encontrado durante la compilacion.

    Atributos:
        fase:    "lexico" | "sintactico" | "semantico"
        linea:   linea del codigo fuente donde ocurre el error (empieza en 1)
        mensaje: descripcion del error, pensada para leerse tal cual
        columna: columna donde empieza el error (empieza en 1), o None si la
                 fase no la conoce (el analisis semantico no la guarda)
    """

    def __init__(self, fase: str, linea: int, mensaje: str, columna: int | None = None):
        self.fase = fase
        self.linea = linea
        self.mensaje = mensaje
        self.columna = columna
        super().__init__(f"[{fase}] línea {linea}: {mensaje}")

    def to_dict(self) -> dict:
        """Devuelve el error como diccionario, listo para exportarse a JSON.
        La columna solo se incluye cuando se conoce."""
        d = {"fase": self.fase, "linea": self.linea, "mensaje": self.mensaje}
        if self.columna is not None:
            d["columna"] = self.columna
        return d
