# Desktop sample data

Place optional demo data here before packaging if you want new desktop users to start with built-in examples.

The folder structure should mirror the runtime `data` directory, for example:

- `books/`
- `chapters/`
- `progress/`
- `vector_db/`

On first launch, the packaged backend copies real files from this folder into the user's Electron app data directory. It writes a `.sample_data_seeded` marker and will not overwrite existing user data on later launches or upgrades.
