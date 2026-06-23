/*
 * Generador del cuestionario de evaluación (usabilidad SUS + utilidad/aceptación)
 * del Sistema Web Geoespacial de Predicción de Incidentes Delictivos — Guayaquil.
 * Salida: Cuestionario_Evaluacion_Sistema.docx
 *
 * Ejecutar:
 *   NODE_PATH="C:/Users/jhono/AppData/Roaming/npm/node_modules" node generar_cuestionario.js
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak,
} = require("docx");

// ── Paleta y constantes ──────────────────────────────────────────────────────
const CONTENT = 9360;            // ancho de contenido (US Letter, márgenes 1")
const AZUL = "1F3864";           // títulos
const AZUL2 = "2E5496";          // encabezados de tabla / subtítulos
const GRIS = "BFBFBF";           // bordes
const FILA_ALT = "F2F6FB";       // sombreado de filas alternas
const ESCALA = "1 = Totalmente en desacuerdo  ·  2 = En desacuerdo  ·  3 = Ni de acuerdo ni en desacuerdo  ·  4 = De acuerdo  ·  5 = Totalmente de acuerdo";

const bd = { style: BorderStyle.SINGLE, size: 1, color: GRIS };
const borders = { top: bd, bottom: bd, left: bd, right: bd };
const cellMargins = { top: 60, bottom: 60, left: 110, right: 110 };

// ── Helpers ──────────────────────────────────────────────────────────────────
const txt = (t, o = {}) => new TextRun({ text: t, ...o });

function p(text, o = {}) {
  return new Paragraph({
    spacing: { after: o.after ?? 120, before: o.before ?? 0, line: o.line ?? 276 },
    alignment: o.align,
    border: o.border,
    children: o.runs ?? [txt(text, o.run ?? {})],
  });
}

function sectionHeading(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 280, after: 140 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: AZUL2, space: 3 } },
    children: [txt(text)],
  });
}

function subHeading(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 180, after: 80 },
    children: [txt(text)],
  });
}

function legend() {
  return p(null, { runs: [txt(ESCALA, { italics: true, size: 17, color: "595959" })], after: 80 });
}

function hcell(text, w, alignCenter = true) {
  return new TableCell({
    borders, width: { size: w, type: WidthType.DXA }, margins: cellMargins,
    shading: { fill: AZUL2, type: ShadingType.CLEAR },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: alignCenter ? AlignmentType.CENTER : AlignmentType.LEFT,
      spacing: { after: 0 },
      children: [txt(text, { bold: true, color: "FFFFFF", size: 19 })],
    })],
  });
}

function bcell(text, w, { center = false, shade = null, bold = false, size = 20 } = {}) {
  return new TableCell({
    borders, width: { size: w, type: WidthType.DXA }, margins: cellMargins,
    shading: shade ? { fill: shade, type: ShadingType.CLEAR } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: center ? AlignmentType.CENTER : AlignmentType.LEFT,
      spacing: { after: 0 },
      children: [txt(text, { size, bold })],
    })],
  });
}

// Tabla Likert: rows = [[code, afirmación], ...]
function likertTable(rows) {
  const W = [520, 5240, 720, 720, 720, 720, 720]; // suma = 9360
  const header = new TableRow({
    tableHeader: true,
    children: [
      hcell("N.°", W[0]), hcell("Afirmación", W[1], false),
      hcell("1", W[2]), hcell("2", W[3]), hcell("3", W[4]), hcell("4", W[5]), hcell("5", W[6]),
    ],
  });
  const body = rows.map((r, i) => {
    const shade = i % 2 === 1 ? FILA_ALT : null;
    return new TableRow({
      children: [
        bcell(r[0], W[0], { center: true, shade, bold: true }),
        bcell(r[1], W[1], { shade }),
        bcell("1", W[2], { center: true, shade }),
        bcell("2", W[3], { center: true, shade }),
        bcell("3", W[4], { center: true, shade }),
        bcell("4", W[5], { center: true, shade }),
        bcell("5", W[6], { center: true, shade }),
      ],
    });
  });
  return new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: W,
    rows: [header, ...body],
  });
}

function checkboxLine(label, options) {
  const runs = [txt(label + ":  ", { bold: true })];
  options.forEach((o) => runs.push(txt("☐ " + o + "    ")));
  return p(null, { runs, after: 100 });
}

function fieldLine(label, fill = 34) {
  return p(null, { runs: [txt(label + ": ", { bold: true }), txt("_".repeat(fill))], after: 100 });
}

function blankLines(n) {
  const arr = [];
  for (let i = 0; i < n; i++) {
    arr.push(new Paragraph({
      spacing: { after: 60, before: 60, line: 360 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: GRIS, space: 2 } },
      children: [txt(" ")],
    }));
  }
  return arr;
}

// ── Contenido ────────────────────────────────────────────────────────────────
const sus = [
  ["1", "Creo que me gustaría utilizar este sistema con frecuencia."],
  ["2", "Encontré el sistema innecesariamente complejo."],
  ["3", "Pensé que el sistema fue fácil de usar."],
  ["4", "Creo que necesitaría el apoyo de una persona técnica para poder utilizar este sistema."],
  ["5", "Encontré que las diversas funciones del sistema estaban bien integradas."],
  ["6", "Pensé que había demasiada inconsistencia en el sistema."],
  ["7", "Imagino que la mayoría de las personas aprenderían a utilizar este sistema muy rápidamente."],
  ["8", "Encontré el sistema muy incómodo (engorroso) de utilizar."],
  ["9", "Me sentí muy confiado(a) y seguro(a) al utilizar el sistema."],
  ["10", "Necesité aprender muchas cosas antes de poder comenzar a utilizar el sistema."],
];

const utilidad = [
  ["11", "El mapa de calor me permite identificar fácilmente las zonas de mayor riesgo."],
  ["12", "Los niveles de gravedad (Baja, Media, Alta y Crítica) son claros y fáciles de entender."],
  ["13", "El indicador de peligrosidad (0–100 %) es fácil de interpretar."],
  ["14", "Los filtros (hora, día, mes, distrito, circuito, subcircuito y tipo de delito) me permiten consultar la información que necesito."],
  ["15", "Las gráficas (horas de mayor riesgo y distribución de la gravedad) aportan información útil."],
  ["16", "La información que entrega el sistema es relevante para mi contexto o necesidad."],
  ["17", "Confío en las predicciones de riesgo que muestra el sistema."],
  ["18", "El tiempo de respuesta del sistema al actualizar una consulta es adecuado."],
];

const intencion = [
  ["19", "Tengo la intención de utilizar este sistema si estuviera disponible."],
  ["20", "Recomendaría este sistema a otras personas."],
  ["21", "Considero que el sistema aporta valor para la prevención y la seguridad en Guayaquil."],
  ["22", "En general, me siento satisfecho(a) con el sistema."],
];

const perfilCiudadania = [
  ["C1", "La información me ayuda a tomar precauciones sobre las zonas y horarios que frecuento."],
  ["C2", "El sistema me resulta útil para planificar desplazamientos más seguros."],
  ["C3", "La información se presenta de forma comprensible para una persona sin conocimientos técnicos."],
];

const perfilSeguridad = [
  ["S1", "La información podría apoyar la planificación de patrullajes."],
  ["S2", "El sistema podría ayudar a distribuir mejor los recursos de seguridad."],
  ["S3", "El nivel de detalle geográfico (subcircuito) es adecuado para el trabajo operativo."],
  ["S4", "Las predicciones por hora y día son pertinentes para la operación policial."],
];

const perfilDecisiones = [
  ["D1", "Las visualizaciones y tendencias complementan los diagnósticos de prevención."],
  ["D2", "El sistema aporta evidencia útil para la toma de decisiones institucionales."],
  ["D3", "La información presentada es suficiente para sustentar políticas o estrategias."],
  ["D4", "El sistema facilita la identificación de patrones delictivos a nivel territorial."],
];

// ── Documento ────────────────────────────────────────────────────────────────
const children = [
  // Portada / encabezado
  p(null, { align: AlignmentType.CENTER, after: 0, runs: [txt("UNIVERSIDAD POLITÉCNICA SALESIANA", { bold: true, size: 26, color: AZUL })] }),
  p(null, { align: AlignmentType.CENTER, after: 200, runs: [txt("Sede Guayaquil  ·  Carrera de Computación", { size: 22 })] }),
  p(null, { align: AlignmentType.CENTER, after: 60, runs: [txt("CUESTIONARIO DE EVALUACIÓN DE USABILIDAD Y UTILIDAD", { bold: true, size: 30, color: AZUL })] }),
  p(null, {
    align: AlignmentType.CENTER, after: 60,
    runs: [txt("Sistema Web Geoespacial para la Predicción de Incidentes Delictivos en Guayaquil", { italics: true, size: 22 })],
  }),
  new Paragraph({
    spacing: { before: 120, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: AZUL2, space: 2 } },
    children: [txt(" ", { size: 4 })],
  }),
  p(null, {
    align: AlignmentType.CENTER, after: 240,
    runs: [txt("Proyecto de titulación  ·  Autores: Jhon Israel Olmedo Olvera y Kenneth Daniel Vera Valenzuela  ·  Tutor: Ing. Joe Llerena Izquierdo", { size: 17, color: "595959" })],
  }),

  // Presentación / consentimiento
  p(null, {
    after: 120,
    runs: [
      txt("Estimado(a) participante: ", { bold: true }),
      txt("agradecemos su colaboración. Este cuestionario evalúa la usabilidad y la utilidad del sistema web que acaba de utilizar. Su participación es "),
      txt("voluntaria y anónima", { bold: true }),
      txt("; la información se usará únicamente con fines académicos. Responder toma entre 8 y 10 minutos. No existen respuestas correctas o incorrectas: nos interesa su opinión sincera."),
    ],
  }),
  p(null, {
    after: 60,
    runs: [
      txt("Instrucciones. ", { bold: true }),
      txt("En las secciones II a V, marque con una "),
      txt("X", { bold: true }),
      txt(" (o encierre) el número que mejor represente su grado de acuerdo con cada afirmación, según la escala:"),
    ],
  }),
  legend(),

  // Sección I — Datos generales
  sectionHeading("Sección I.  Datos generales"),
  fieldLine("Fecha", 22),
  checkboxLine("Edad", ["18–25", "26–35", "36–45", "46–60", "más de 60"]),
  checkboxLine("Sexo", ["Femenino", "Masculino", "Prefiero no decirlo"]),
  checkboxLine("Nivel de instrucción", ["Secundaria", "Técnico/Tecnológico", "Universitario", "Posgrado"]),
  checkboxLine("Perfil de usuario", ["Ciudadanía general", "Organismo de seguridad pública", "Tomador(a) de decisiones institucional"]),
  checkboxLine("¿Con qué frecuencia usa aplicaciones de mapas (Google Maps, Waze, etc.)?", ["Nunca", "A veces", "Frecuentemente", "A diario"]),
  checkboxLine("Modo de uso en esta evaluación", ["Demostración guiada", "Uso libre"]),

  // Sección II — SUS
  sectionHeading("Sección II.  Usabilidad del sistema (escala SUS)"),
  legend(),
  likertTable(sus),

  // Sección III — Utilidad
  sectionHeading("Sección III.  Utilidad percibida y calidad de la información"),
  legend(),
  likertTable(utilidad),

  // Sección IV — Intención de uso
  sectionHeading("Sección IV.  Intención de uso y aceptación"),
  legend(),
  likertTable(intencion),

  // Sección V — por perfil
  new Paragraph({ pageBreakBefore: true, children: [] }),
  sectionHeading("Sección V.  Preguntas según su perfil"),
  p(null, {
    after: 120,
    runs: [
      txt("Responda únicamente el bloque que corresponde al perfil que marcó en la Sección I. ", { bold: true }),
      txt("Si se identifica con más de uno, puede responder los que apliquen."),
    ],
  }),
  legend(),
  subHeading("V.A  Ciudadanía general"),
  likertTable(perfilCiudadania),
  subHeading("V.B  Organismos de seguridad pública"),
  likertTable(perfilSeguridad),
  subHeading("V.C  Tomadores de decisiones institucionales"),
  likertTable(perfilDecisiones),

  // Sección VI — abiertas
  sectionHeading("Sección VI.  Preguntas abiertas"),
  p("1.  ¿Qué fue lo que más le gustó del sistema?", { after: 60, run: { bold: true } }),
  ...blankLines(2),
  p("2.  ¿Qué dificultades o problemas encontró al utilizarlo?", { after: 60, before: 80, run: { bold: true } }),
  ...blankLines(2),
  p("3.  ¿Qué mejoras o funciones adicionales sugeriría?", { after: 60, before: 80, run: { bold: true } }),
  ...blankLines(2),

  p(null, {
    align: AlignmentType.CENTER, before: 200,
    runs: [txt("¡Gracias por su tiempo y colaboración!", { bold: true, color: AZUL, size: 22 })],
  }),

  // Anexo investigador
  new Paragraph({ pageBreakBefore: true, children: [] }),
  sectionHeading("Anexo A.  Cálculo del puntaje SUS  (uso del investigador — no se entrega al encuestado)"),
  p(null, {
    after: 120,
    runs: [
      txt("La escala SUS (Sección II) se compone de 10 ítems alternados (positivos y negativos). El puntaje se calcula así:"),
    ],
  }),
  p("a)  Ítems impares (1, 3, 5, 7, 9):  contribución = (valor marcado − 1).", { after: 40 }),
  p("b)  Ítems pares (2, 4, 6, 8, 10):  contribución = (5 − valor marcado).", { after: 40 }),
  p("c)  Sume las 10 contribuciones (rango 0–40) y multiplique por 2.5 para obtener el puntaje SUS (rango 0–100).", { after: 120 }),
  p(null, {
    after: 120,
    runs: [
      txt("Interpretación de referencia: ", { bold: true }),
      txt("un puntaje de 68 corresponde al promedio. Por encima de 68 se considera por encima del promedio; por debajo, requiere mejoras."),
    ],
  }),
  new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: [2340, 2340, 4680],
    rows: [
      new TableRow({ tableHeader: true, children: [hcell("Puntaje SUS", 2340), hcell("Grado", 2340), hcell("Valoración (adjetivo)", 4680, false)] }),
      new TableRow({ children: [bcell("85 – 100", 2340, { center: true }), bcell("A", 2340, { center: true }), bcell("Excelente", 4680)] }),
      new TableRow({ children: [bcell("69 – 84", 2340, { center: true, shade: FILA_ALT }), bcell("B", 2340, { center: true, shade: FILA_ALT }), bcell("Bueno (aceptable)", 4680, { shade: FILA_ALT })] }),
      new TableRow({ children: [bcell("68", 2340, { center: true }), bcell("C", 2340, { center: true }), bcell("Promedio / aceptable", 4680)] }),
      new TableRow({ children: [bcell("51 – 67", 2340, { center: true, shade: FILA_ALT }), bcell("D", 2340, { center: true, shade: FILA_ALT }), bcell("Marginal (requiere mejoras)", 4680, { shade: FILA_ALT })] }),
      new TableRow({ children: [bcell("0 – 50", 2340, { center: true }), bcell("F", 2340, { center: true }), bcell("No aceptable", 4680)] }),
    ],
  }),
  p(null, {
    before: 160,
    runs: [
      txt("Secciones III, IV y V: ", { bold: true }),
      txt("se analizan promediando los valores (1–5) por dimensión (utilidad percibida, calidad de la información, intención de uso y aceptación, y cada bloque por perfil). Un promedio ≥ 4 indica una valoración favorable."),
    ],
  }),
];

const doc = new Document({
  creator: "Proyecto de titulación — UPS Guayaquil",
  title: "Cuestionario de Evaluación — Sistema Predictivo de Incidentes Delictivos",
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: AZUL },
        paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Arial", color: AZUL2 },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 1 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, right: 1440, bottom: 1080, left: 1440 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          spacing: { after: 0 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 3, color: GRIS, space: 2 } },
          children: [txt("Evaluación del Sistema Predictivo de Incidentes Delictivos · UPS Guayaquil", { size: 15, color: "808080" })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0 },
          children: [txt("Página ", { size: 16, color: "808080" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "808080" })],
        })],
      }),
    },
    children,
  }],
});

const out = path.join(__dirname, "Cuestionario_Evaluacion_Sistema.docx");
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(out, buf);
  console.log("Generado:", out, "(" + buf.length + " bytes)");
});
