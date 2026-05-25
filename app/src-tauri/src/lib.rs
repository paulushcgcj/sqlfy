// src-tauri/src/lib.rs
// Register Tauri plugins needed for the CLI bridge.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())   // spawn python CLI
        .plugin(tauri_plugin_fs::init())      // read/write migration files
        .plugin(tauri_plugin_dialog::init())  // folder picker
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}