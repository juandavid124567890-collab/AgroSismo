"""Preguntas frecuentes y soluciones de AgroSismo (pantalla de Ayuda).

Cada pregunta: (pregunta, explicación, [pasos opcionales]).
`nivel` decide quién ve la sección: todos, solo administradores o solo el desarrollador.
"""

TODOS, ADMIN, DESARROLLADOR = "todos", "admin", "desarrollador"

SECCIONES = [
    {
        "id": "primeros-pasos", "titulo": "Primeros pasos", "nivel": TODOS,
        "preguntas": [
            ("¿Cómo ingreso a AgroSismo?",
             "Escribe tu nombre de usuario y tu contraseña en «Iniciar sesión». Si marcas «Recordarme», no tendrás que escribirlos cada vez en ese celular. Si aún no tienes cuenta, escríbenos por WhatsApp y te la creamos.",
             []),
            ("¿Cómo instalo AgroSismo en el celular?",
             "AgroSismo se instala como una aplicación y queda con su ícono en la pantalla de inicio.",
             ["Android (Chrome): toca el menú ⋮ y elige «Instalar aplicación» o «Añadir a la pantalla de inicio».",
              "iPhone (Safari): toca el botón Compartir y elige «Añadir a pantalla de inicio»."]),
            ("¿Qué es una finca y qué es una unidad agrícola?",
             "La finca es tu grupo de trabajo: tu finca o empresa, con su administrador y sus trabajadores. Todos los de la misma finca ven los mismos datos. La unidad agrícola es cada lote o terreno dentro de la finca, con su área, su ubicación y sus cultivos.",
             []),
            ("¿Quién puede ver mis datos?",
             "Solo las personas de tu finca. Ninguna otra finca puede ver tus unidades, sismos, afectaciones, fotos ni reportes.",
             []),
        ],
    },
    {
        "id": "registrar", "titulo": "Registrar un sismo y sus daños", "nivel": TODOS,
        "preguntas": [
            ("¿Cómo registro un sismo?",
             "Primero debes tener al menos una unidad agrícola creada en «Mis unidades».",
             ["Entra a «Sismos» y toca «Nuevo sismo».",
              "Elige la unidad agrícola y escribe la fecha y la hora en que se sintió.",
              "La magnitud y el epicentro son opcionales: solo escríbelos si los conoces.",
              "Toca «Guardar»."]),
            ("¿Cómo registro los daños que dejó el sismo?",
             "Los daños se registran dentro del sismo.",
             ["Entra al sismo desde «Sismos».",
              "Toca «Registrar afectación».",
              "Elige qué se dañó (terreno, cultivo, construcción…), el tipo de daño, la severidad y el área afectada en hectáreas.",
              "Si hubo pérdidas, anota la cantidad y el valor en pesos. Luego guarda."]),
            ("¿Qué significa leve, moderada y grave?",
             "Es el nivel del daño según lo que tú observas. Leve: daño pequeño que no frena el trabajo. Moderada: daño importante que reduce la producción o exige reparar. Grave: daño muy fuerte o pérdida casi total.",
             []),
            ("Elegí «Otro» como tipo de daño. ¿Qué escribo?",
             "Al elegir «Otro» aparece un cuadro para que escribas cuál fue el daño con tus palabras (por ejemplo, «Se cayó la cerca»). Es obligatorio. Ese texto sale en el detalle, el historial y el reporte.",
             []),
            ("¿Cómo agrego fotografías?",
             "Puedes agregar hasta 10 fotos por afectación y cada una puede pesar hasta 5 MB. Se agregan desde el detalle de la afectación. Las fotos solo las ve tu finca.",
             []),
            ("¿Cómo escribo el valor de las pérdidas?",
             "Escribe solo números, sin puntos ni signos. El sistema pone los puntos de mil y el signo de pesos por ti. Por ejemplo, si escribes 1500000 verás $1.500.000. Recuerda que son estimaciones tuyas, no una valoración técnica oficial.",
             []),
        ],
    },
    {
        "id": "errores", "titulo": "Me salió un aviso o un error", "nivel": TODOS,
        "preguntas": [
            ("«El área afectada supera el área de la unidad»",
             "Escribiste más hectáreas dañadas de las que tiene la unidad. Revisa el número. Si el área de la unidad está mal, corrígela en «Mis unidades».",
             []),
            ("«La fecha del sismo no puede estar en el futuro»",
             "Revisa la fecha y la hora que escribiste. Debe ser un momento que ya pasó.",
             []),
            ("«Ya se registró un sismo en esa unidad y fecha»",
             "Alguien de tu finca ya registró ese sismo. No lo repitas: entra a «Sismos», ábrelo y usa «Registrar afectación» para agregar tus daños.",
             []),
            ("«Ya hay una unidad con ese nombre en tu finca»",
             "Los nombres de las unidades no se pueden repetir dentro de la misma finca. Cambia el nombre (por ejemplo, «Lote Norte» y «Lote Sur»).",
             []),
            ("«Tu finca está desactivada»",
             "El acceso de tu finca fue pausado. Tus datos no se han perdido. Escríbenos por WhatsApp y la volvemos a activar.",
             []),
            ("La página se ve vieja o no aparecen cambios",
             "El celular puede estar mostrando una copia guardada. Cierra la aplicación por completo y ábrela de nuevo con internet. Si sigue igual, recarga la página deslizando hacia abajo.",
             []),
        ],
    },
    {
        "id": "sin-internet", "titulo": "Trabajar sin internet", "nivel": TODOS,
        "preguntas": [
            ("¿Puedo registrar un sismo sin internet?",
             "Sí. Usa el «Registro rápido»: guarda el sismo y los daños en tu celular y los envía solo cuando vuelve la señal. No tienes que hacer nada más.",
             ["Abre «Registro rápido» (en el inicio).",
              "Llena el sismo y la afectación, y guarda.",
              "Cuando haya internet, los registros pendientes se envían solos."]),
            ("Sin internet no me aparecen mis unidades",
             "El celular necesita descargarlas una vez. Abre AgroSismo con internet e inicia sesión. Después de eso, tus unidades quedan guardadas para usarlas sin conexión.",
             []),
            ("¿Cómo sé si mis registros ya se enviaron?",
             "En «Registro rápido», la lista «Por enviar» muestra cada registro como pendiente o enviado. Cuando se envían quedan marcados, y puedes quitarlos de la lista con «Limpiar enviados».",
             []),
            ("Un registro no se pudo enviar",
             "Casi siempre es porque un dato no es válido (por ejemplo, un área mayor a la de la unidad). Abre el registro pendiente, revisa el aviso que aparece y corrígelo. Si no lo entiendes, escríbenos por WhatsApp.",
             []),
        ],
    },
    {
        "id": "reportes", "titulo": "Historial y reportes", "nivel": TODOS,
        "preguntas": [
            ("¿Cómo descargo un reporte en PDF?",
             "El reporte reúne tus afectaciones con fechas, severidad y pérdidas estimadas, listo para entregar.",
             ["Entra a «Reportes».",
              "Elige el rango de fechas y, si quieres, la unidad o la severidad.",
              "Toca «Ver vista previa» para revisar y luego «Exportar en PDF»."]),
            ("¿Cómo encuentro un registro antiguo?",
             "Entra a «Historial» y usa los filtros: fecha del sismo, unidad agrícola o severidad. También puedes buscar sismos por unidad, fecha o epicentro en «Sismos».",
             []),
            ("¿Qué muestra la gráfica del inicio?",
             "Las afectaciones por mes. Con los botones de arriba cambias el período: últimos 7 días, 3, 6 o 12 meses.",
             []),
        ],
    },
    {
        "id": "cuenta", "titulo": "Mi cuenta", "nivel": TODOS,
        "preguntas": [
            ("Olvidé mi contraseña",
             "No necesitas crear otra cuenta.",
             ["En «Iniciar sesión» toca «¿Olvidaste tu contraseña?».",
              "Escribe tu nombre de usuario y, si quieres, cómo contactarte.",
              "El administrador recibe tu solicitud y te entrega una contraseña nueva. Si tardan, escríbenos por WhatsApp."]),
            ("No me deja ingresar",
             "Revisa que el nombre de usuario y la contraseña estén bien escritos (cuida las mayúsculas). Si tu cuenta o tu finca fue desactivada, el aviso lo dice. Si nada de eso sirve, solicita una contraseña nueva o escríbenos.",
             []),
        ],
    },
    {
        "id": "administrador", "titulo": "Para administradores de finca", "nivel": ADMIN,
        "preguntas": [
            ("¿Cómo creo la cuenta de un trabajador?",
             "Solo puedes crear cuentas para tu propia finca.",
             ["Entra a «Usuarios» y toca «Nueva cuenta».",
              "Escribe su nombre y su usuario, y elige el rol.",
              "Al guardar, el sistema te muestra la contraseña temporal una sola vez. Anótala y entrégala a la persona."]),
            ("¿Cómo atiendo una solicitud de contraseña?",
             "En «Usuarios» aparecen las solicitudes pendientes de tu finca. Toca «Restablecer clave», copia la contraseña nueva y entrégala a la persona. También puedes «Descartar» la solicitud.",
             []),
            ("¿Cómo desactivo la cuenta de alguien que se retiró?",
             "En «Usuarios», busca la cuenta y toca «Desactivar». No podrá ingresar, pero sus datos se conservan y puedes reactivarla cuando quieras.",
             []),
        ],
    },
    {
        "id": "desarrollador", "titulo": "Para el desarrollador", "nivel": DESARROLLADOR,
        "preguntas": [
            ("¿Cómo creo una finca nueva y su administrador?",
             "Solo el desarrollador crea fincas.",
             ["Entra a «Fincas» y toca «Nueva finca».",
              "Escribe el nombre y guarda: el sistema te lleva a crear su administrador con la finca ya elegida.",
              "Entrega el usuario y la contraseña temporal al administrador."]),
            ("¿Cuándo desactivar y cuándo eliminar una finca?",
             "Desactívala si solo se retiran por un tiempo: sus usuarios no pueden ingresar y nada se pierde. Elimínala solo si no volverán: se borran para siempre sus usuarios, unidades, sismos, afectaciones, fotos y reportes, y por eso el sistema pide escribir el nombre exacto de la finca.",
             []),
        ],
    },
]


def secciones_para(usuario):
    """Secciones que puede ver quien consulta la ayuda (público, administrador o desarrollador)."""
    permitidos = {TODOS}
    if getattr(usuario, "is_authenticated", False):
        if getattr(usuario, "es_admin", False):
            permitidos.add(ADMIN)
        if getattr(usuario, "es_desarrollador", False):
            permitidos.add(DESARROLLADOR)
    return [s for s in SECCIONES if s["nivel"] in permitidos]
