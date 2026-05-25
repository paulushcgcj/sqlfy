# sqlfy — Desktop App

React + Vite + Tauri desktop UI for the SQLfy schema graph engine.

## Dev

```bash
npm install
npm run dev        # Vite browser dev server (http://localhost:5173)
npx tauri dev      # Tauri desktop window (requires Rust toolchain)
```

## Build

```bash
npm run build      # Vite production build → dist/
npx tauri build    # Tauri bundle → src-tauri/target/release/bundle/
```

## Lint

```bash
npm run lint
```

## Notes

- SQL samples are loaded from `../samples/*.sql` via `import.meta.glob` at build time.
  Add or edit `.sql` files there to update the preloaded demo content.
- `vite.config.ts` sets `server.fs.allow: ['..']` so the dev server can serve files
  from the repo root during development.
