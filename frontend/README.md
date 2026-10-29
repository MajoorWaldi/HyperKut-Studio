# HyperKut Studio frontend

React/TypeScript interface for the local HyperKut backend. The entire Studio is beta; finishing controls are experimental.

## Development

Node.js 22+ and npm are required. From this directory:

```powershell
npm ci
npm run dev
```

The Vite development server is separate from the Python backend and ComfyUI. Use the project's existing Vite configuration for API proxying.

## Build and checks

```powershell
npm run build
npm test
npm run lint
```

The production build is written to `dist/` and served by the Studio backend. No Node web server is required to serve that built interface; requested HyperFrames graphics still need Node.

[Project README](../README.md) · [Installation](../docs/installation.md) · [Roadmap](../ROADMAP.md)
