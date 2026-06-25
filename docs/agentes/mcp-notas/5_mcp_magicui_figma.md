# 🪄 MCP 5: Magic UI MCP & Figma MCP (Diseño Frontend Rápido)

Para crear la **Landing Page Pública (PQRS_LANDING)** y la nueva interfaz de la aplicación interna de forma veloz y estandarizada, vamos a utilizar estos dos servidores de diseño orientados a React y TailwindCSS.

Con estas herramientas instaladas, evitaremos programar de cero botones, efectos "Glassmorphism" o de iluminación.

## 🎨 1. Figma MCP (El Puente del Diseño)
Este MCP extrae la información y jerarquías directamente de tus lienzos de diseño (o de los autogenerados por Google Stitch) y los convierte en código.
- **Instalación:**
  1. Abre **Settings > MCP Servers** en tu editor.
  2. Haz clic en **Add New**.
  3. Nombre: `figma-mcp` / Comando: `npx -y @modelcontextprotocol/server-figma`
  4. Necesitarás agregar la variable de entorno: `FIGMA_ACCESS_TOKEN`. (Puedes generar uno en tu cuenta de Figma en *"Settings > Personal Access Tokens"*).

## 🧩 2. Magic UI MCP (El Catálogo de Componentes)
Este es un repositorio vivo de los mejores componentes modernos de Internet (Modo oscuro, cursores dinámicos, fondos animados de resplandor, "Marquees" de empresas clientes, etc).
- **Instalación:**
  1. En **Settings > MCP Servers**, dale a **Add New**.
  2. Nombre: `magic-ui` / Comando: `npx -y @magicui/mcp`
  *(Nota: dependiendo de las últimas actualizaciones, Magic UI suele venir integrado junto a los componentes nativos, o puede requerir simplemente inicializar el CLI en el proyecto frontend con `npx magic-ui init` en lugar del MCP, pero tener el conector permite pedir cosas como "armame un Hero resplandeciente" y que yo incruste las clases Tailwind necesarias mágicamente).*

---

### ¿Cómo los usaremos juntos en V2 y Landing?
Cuando arranquemos la fase visual, yo te diré:
*"Ve a Google Stitch o Figma, aprueba el diseño, páseme el enlace y yo lo transformaré pixel-perfect utilizando los componentes resplandecientes de Magic UI."*
