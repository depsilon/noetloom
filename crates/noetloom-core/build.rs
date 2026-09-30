use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use sha2::{Digest, Sha256};

fn rust_files(directory: &Path, files: &mut Vec<PathBuf>) {
    for entry in fs::read_dir(directory).expect("source directory") {
        let entry = entry.expect("source entry");
        let kind = entry.file_type().expect("source file type");
        assert!(!kind.is_symlink(), "source symlinks are unsupported");
        if kind.is_dir() {
            rust_files(&entry.path(), files);
        } else if entry
            .path()
            .extension()
            .is_some_and(|extension| extension == "rs")
        {
            files.push(entry.path());
        }
    }
}

fn main() {
    let crate_root = PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").unwrap());
    let root = crate_root.parent().unwrap().parent().unwrap();
    let mut files = vec![
        root.join("Cargo.toml"),
        root.join("Cargo.lock"),
        root.join("rust-toolchain.toml"),
        crate_root.join("Cargo.toml"),
    ];
    rust_files(&crate_root, &mut files);
    files.sort();
    let entries: Vec<(String, String)> = files
        .iter()
        .map(|path| {
            assert!(
                !fs::symlink_metadata(path).unwrap().file_type().is_symlink(),
                "source symlinks are unsupported"
            );
            println!("cargo:rerun-if-changed={}", path.display());
            let relative = path
                .strip_prefix(root)
                .unwrap()
                .to_str()
                .unwrap()
                .replace('\\', "/");
            let bytes = fs::read(path).expect("source bytes");
            (relative, format!("{:x}", Sha256::digest(bytes)))
        })
        .collect();
    // Watching the directory also detects newly added source files.
    println!("cargo:rerun-if-changed={}", crate_root.display());
    let source_sha256 = format!(
        "{:x}",
        Sha256::digest(serde_json::to_vec(&entries).unwrap())
    );
    let rustc = Command::new(env::var_os("RUSTC").unwrap())
        .arg("-Vv")
        .output()
        .expect("compiler identity");
    assert!(rustc.status.success(), "compiler identity failed");
    let identity = serde_json::json!({
        "schema": "noetloom.rust_build.v1",
        "source_sha256": source_sha256,
        "source_files": entries,
        "rustc": String::from_utf8(rustc.stdout).unwrap().trim(),
        "target": env::var("TARGET").unwrap(),
        "profile": env::var("PROFILE").unwrap(),
        "package_version": env::var("CARGO_PKG_VERSION").unwrap(),
        "rustflags": env::var("CARGO_ENCODED_RUSTFLAGS").unwrap_or_default(),
    });
    fs::write(
        PathBuf::from(env::var_os("OUT_DIR").unwrap()).join("build-identity.json"),
        serde_json::to_vec(&identity).unwrap(),
    )
    .unwrap();
}
