# TEMPLATE_ESCENARIO_QA.md

## Escenario de Atributo de Calidad: [Nombre del Atributo]

| Campo | Descripción / Redacción Técnica |
| :--- | :--- |
| **Atributo:** | [Nombre del Atributo de Calidad y sub-categoría/foco, ej: Seguridad (Autorización y Privacidad)] |
| **Origen:** | [Entidad que genera el estímulo: usuario autenticado, atacante externo, sistema de tercero, infraestructura subyacente, equipo de desarrollo, etc.] |
| **Estímulo:** | [Condición o evento que llega al sistema: ráfaga de peticiones, fallo de nodo, solicitud de integración, consulta bajo carga, etc.] |
| **Artefacto:** | [Componente, servicio, módulo o capa del sistema que recibe el impacto del estímulo] |
| **Contexto:** | [Condición operativa en la que ocurre el evento: producción bajo carga pico, hora de inicio de jornada, tiempo de desarrollo, red móvil inestable, etc.] |
| **Respuesta:** | [Comportamiento observable del sistema ante el estímulo. **REGLA ESTRICTA:** Debe ser un comportamiento de negocio/sistema puro, SIN incluir tácticas ni soluciones arquitectónicas de implementación] |
| **Medida de respuesta:** | [Métrica cuantitativa y objetiva para validar si la respuesta es satisfactoria: percentiles (p95, p90), tiempos máximos (ms/s/min), disponibilidad (SLA), esfuerzo en semanas, % de componentes afectados, etc.] |

---
