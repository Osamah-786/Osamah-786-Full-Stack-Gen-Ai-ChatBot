# Public static files

`favicon.svg` and `icons.svg` are served by Vite from the public root without import/bundling. `index.html` references the browser page metadata/root mount; Vite copies public assets to the build output. Do not place private configuration or server secrets in this folder.
