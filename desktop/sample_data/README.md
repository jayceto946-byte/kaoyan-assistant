# Desktop sample data

This directory is the local packaging input for built-in desktop demo resources. The packaged backend copies files from here into the user's Electron data directory on first launch without overwriting existing user files.

Expected runtime-shaped folders:

- `books/`
- `chapters/`
- `images/`
- `progress/`
- `vector_db/`
- `models/`

Large files in this directory are intentionally ignored by Git. Before building a desktop installer locally, run:

```powershell
.\scripts\prepare-desktop-sample-data.ps1 -SourceData .\kaoyan-assistant\data -BookName 优化设计
```

`build-desktop-backend.ps1` runs that preparation automatically when `kaoyan-assistant\data` exists.