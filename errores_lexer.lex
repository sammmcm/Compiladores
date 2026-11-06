{
  "exito": false,
  "total_tokens": 20,
  "tokens": [
    {
      "tipo": "IDENTIFICADOR",
      "lexema": "x",
      "linea": 1,
      "columna": 1
    },
    {
      "tipo": "OP_ASIGNACION",
      "lexema": "=",
      "linea": 1,
      "columna": 3
    },
    {
      "tipo": "PUNTOCOMA",
      "lexema": ";",
      "linea": 1,
      "columna": 7
    },
    {
      "tipo": "IDENTIFICADOR",
      "lexema": "y",
      "linea": 2,
      "columna": 1
    },
    {
      "tipo": "OP_ASIGNACION",
      "lexema": "=",
      "linea": 2,
      "columna": 3
    },
    {
      "tipo": "OP_ARITMETICO",
      "lexema": "+",
      "linea": 2,
      "columna": 7
    },
    {
      "tipo": "NUMERO",
      "lexema": "2",
      "linea": 2,
      "columna": 9
    },
    {
      "tipo": "PUNTOCOMA",
      "lexema": ";",
      "linea": 2,
      "columna": 10
    },
    {
      "tipo": "IDENTIFICADOR",
      "lexema": "msg",
      "linea": 3,
      "columna": 1
    },
    {
      "tipo": "OP_ASIGNACION",
      "lexema": "=",
      "linea": 3,
      "columna": 5
    },
    {
      "tipo": "IDENTIFICADOR",
      "lexema": "z",
      "linea": 4,
      "columna": 1
    },
    {
      "tipo": "OP_ASIGNACION",
      "lexema": "=",
      "linea": 4,
      "columna": 3
    },
    {
      "tipo": "OP_ARITMETICO",
      "lexema": "*",
      "linea": 4,
      "columna": 10
    },
    {
      "tipo": "NUMERO",
      "lexema": "1.5e-3",
      "linea": 4,
      "columna": 12
    },
    {
      "tipo": "PUNTOCOMA",
      "lexema": ";",
      "linea": 4,
      "columna": 18
    },
    {
      "tipo": "IDENTIFICADOR",
      "lexema": "total",
      "linea": 5,
      "columna": 1
    },
    {
      "tipo": "OP_ASIGNACION",
      "lexema": "=",
      "linea": 5,
      "columna": 7
    },
    {
      "tipo": "IDENTIFICADOR",
      "lexema": "x",
      "linea": 5,
      "columna": 9
    },
    {
      "tipo": "IDENTIFICADOR",
      "lexema": "y",
      "linea": 5,
      "columna": 13
    },
    {
      "tipo": "PUNTOCOMA",
      "lexema": ";",
      "linea": 5,
      "columna": 14
    }
  ],
  "errores": [
    {
      "fase": "lexico",
      "linea": 1,
      "mensaje": "Número mal formado: '3.'",
      "columna": 5
    },
    {
      "fase": "lexico",
      "linea": 2,
      "mensaje": "Carácter no reconocido: '@'",
      "columna": 5
    },
    {
      "fase": "lexico",
      "linea": 3,
      "mensaje": "Cadena sin cerrar: \"hola mundo;",
      "columna": 7
    },
    {
      "fase": "lexico",
      "linea": 4,
      "mensaje": "Número mal formado: '7abc'",
      "columna": 5
    },
    {
      "fase": "lexico",
      "linea": 5,
      "mensaje": "Carácter no reconocido: '$'",
      "columna": 11
    }
  ]
}