//! Immutable payloads and snapshots with an atomic, revision-checked commit pointer.
use std::collections::BTreeMap;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::value::{CellRef, Value};
use crate::{Error, Result};

static TEMP_SEQUENCE: AtomicU64 = AtomicU64::new(0);

pub fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StoreLimits {
    pub max_cells: usize,
    pub max_blob_bytes: u64,
    pub max_metadata_bytes: u64,
    /// Includes retained snapshots, payloads, and temporary files.
    pub max_store_bytes: u64,
    /// Separate from activation I/O: verifying already-present immutable files.
    pub max_commit_validation_bytes: u64,
}

impl Default for StoreLimits {
    fn default() -> Self {
        Self {
            max_cells: 256,
            max_blob_bytes: 1 << 20,
            max_metadata_bytes: 1 << 20,
            max_store_bytes: 8 << 20,
            max_commit_validation_bytes: 1 << 20,
        }
    }
}

impl StoreLimits {
    fn validate(self) -> Result<()> {
        if self.max_cells == 0
            || self.max_blob_bytes == 0
            || self.max_metadata_bytes == 0
            || self.max_store_bytes == 0
        {
            return Err(Error::new(
                "invalid_limits",
                "store limits must be positive",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct CellRecord {
    revision: u64,
    blob_sha256: String,
    byte_len: u64,
    value_bytes: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Snapshot {
    schema: String,
    generation: u64,
    parent: Option<String>,
    cells: BTreeMap<u64, CellRecord>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReadMetrics {
    pub payload_reads: u64,
    pub payload_bytes: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CommitReceipt {
    pub before: String,
    pub after: String,
    pub generation: u64,
    pub changed_cells: Vec<CellRef>,
    pub new_file_bytes: u64,
    pub validation_reads: u64,
    pub validation_bytes: u64,
    pub reads: ReadMetrics,
}

#[derive(Debug)]
pub struct Store {
    root: PathBuf,
    limits: StoreLimits,
    snapshot_id: String,
    snapshot: Snapshot,
    pub metadata_bytes_read: u64,
}

#[derive(Clone, Copy, Debug)]
pub struct ReadAdmission {
    pub payload_bytes: u64,
    pub value_bytes: u64,
}

struct Staged {
    revision: u64,
    value: Value,
    encoded: Vec<u8>,
}

pub struct Transaction<'a> {
    store: &'a Store,
    staged: BTreeMap<u64, Staged>,
    staged_bytes: u64,
    reads: ReadMetrics,
}

fn valid_digest(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn directory(path: &Path) -> Result<()> {
    if !fs::symlink_metadata(path)?.file_type().is_dir() {
        return Err(Error::new(
            "invalid_store",
            format!("{} is not a plain directory", path.display()),
        ));
    }
    Ok(())
}

fn read_bounded(path: &Path, max_bytes: u64) -> Result<Vec<u8>> {
    let metadata = fs::symlink_metadata(path)?;
    if !metadata.file_type().is_file() || metadata.len() > max_bytes {
        return Err(Error::new(
            "invalid_store",
            format!("{} is not a bounded regular file", path.display()),
        ));
    }
    let file = File::open(path)?;
    let mut bytes = Vec::new();
    file.take(max_bytes.saturating_add(1))
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > max_bytes {
        return Err(Error::new(
            "invalid_store",
            "file grew beyond its admitted size",
        ));
    }
    Ok(bytes)
}

fn current(root: &Path) -> Result<String> {
    let bytes = read_bounded(&root.join("CURRENT"), 65)?;
    let value = std::str::from_utf8(&bytes)
        .map_err(|_| Error::new("invalid_store", "CURRENT is not UTF-8"))?;
    let value = value.strip_suffix('\n').unwrap_or(value);
    if !valid_digest(value) {
        return Err(Error::new(
            "invalid_store",
            "CURRENT is not a snapshot digest",
        ));
    }
    Ok(value.to_owned())
}

fn create_file(path: &Path, bytes: &[u8]) -> Result<()> {
    let mut file = OpenOptions::new().write(true).create_new(true).open(path)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    Ok(())
}

fn immutable_file(path: &Path, bytes: &[u8]) -> Result<u64> {
    if path.try_exists()? {
        if read_bounded(path, bytes.len() as u64)? != bytes {
            return Err(Error::new(
                "hash_mismatch",
                "existing immutable file has different content",
            ));
        }
        return Ok(0);
    }
    let parent = path
        .parent()
        .ok_or_else(|| Error::new("invalid_store", "immutable file has no directory"))?;
    let mut pending = None;
    for _ in 0..1024 {
        let sequence = TEMP_SEQUENCE.fetch_add(1, Ordering::Relaxed);
        let candidate = parent.join(format!(".pending-{}-{sequence}", std::process::id()));
        match OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&candidate)
        {
            Ok(mut file) => {
                // Interrupted writes remain outside the content-addressed namespace.
                // Retain partial pending files for accounting and inspection.
                file.write_all(bytes)?;
                file.sync_all()?;
                pending = Some(candidate);
                break;
            }
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(error) => return Err(error.into()),
        }
    }
    let pending = pending.ok_or_else(|| {
        Error::new(
            "invalid_store",
            "too many retained pending files; inspect the store",
        )
    })?;
    // Hard-link publication is atomic and cannot overwrite an existing immutable file.
    // Both paths are in the same directory/filesystem; commits hold the writer lock.
    fs::hard_link(&pending, path)?;
    fs::remove_file(&pending)?;
    Ok(bytes.len() as u64)
}

// Directory sync is required for the supported Linux/macOS durability contract.
fn sync_directory(path: &Path) -> Result<()> {
    File::open(path)?.sync_all()?;
    Ok(())
}

fn store_bytes(root: &Path) -> Result<u64> {
    let mut total = 0_u64;
    for entry in fs::read_dir(root)? {
        let entry = entry?;
        let metadata = fs::symlink_metadata(entry.path())?;
        if metadata.file_type().is_file() {
            total = total
                .checked_add(metadata.len())
                .ok_or_else(|| Error::new("store_budget", "size overflow"))?;
        } else if metadata.file_type().is_dir()
            && (entry.file_name() == "blobs" || entry.file_name() == "snapshots")
        {
            for child in fs::read_dir(entry.path())? {
                let metadata = fs::symlink_metadata(child?.path())?;
                if !metadata.file_type().is_file() {
                    return Err(Error::new(
                        "invalid_store",
                        "immutable directories must contain regular files",
                    ));
                }
                total = total
                    .checked_add(metadata.len())
                    .ok_or_else(|| Error::new("store_budget", "size overflow"))?;
            }
        } else {
            return Err(Error::new(
                "invalid_store",
                "unexpected directory or special file in store",
            ));
        }
    }
    Ok(total)
}

impl Store {
    /// Requires a new directory; never initializes over an existing store.
    pub fn create(root: impl AsRef<Path>, limits: StoreLimits) -> Result<Self> {
        limits.validate()?;
        let root = root.as_ref();
        let snapshot = Snapshot {
            schema: "noetloom.state.v1".into(),
            generation: 0,
            parent: None,
            cells: BTreeMap::new(),
        };
        let bytes = serde_json::to_vec(&snapshot)?;
        if bytes.len() as u64 > limits.max_metadata_bytes
            || bytes.len() as u64 + 65 > limits.max_store_bytes
        {
            return Err(Error::new(
                "store_budget",
                "initial snapshot exceeds budget",
            ));
        }
        fs::create_dir(root)?;
        fs::create_dir(root.join("blobs"))?;
        fs::create_dir(root.join("snapshots"))?;
        create_file(&root.join("WRITER.lock"), &[])?;
        let digest = sha256(&bytes);
        create_file(
            &root.join("snapshots").join(format!("{digest}.json")),
            &bytes,
        )?;
        sync_directory(&root.join("snapshots"))?;
        create_file(&root.join("CURRENT"), format!("{digest}\n").as_bytes())?;
        sync_directory(root)?;
        if let Some(parent) = root.parent().filter(|path| !path.as_os_str().is_empty()) {
            sync_directory(parent)?;
        }
        Self::open(root, limits)
    }

    /// Loads only pointer/index metadata. Payload validation occurs on activation.
    pub fn open(root: impl AsRef<Path>, limits: StoreLimits) -> Result<Self> {
        limits.validate()?;
        let root = root.as_ref().to_path_buf();
        directory(&root)?;
        directory(&root.join("blobs"))?;
        directory(&root.join("snapshots"))?;
        let snapshot_id = current(&root)?;
        let bytes = read_bounded(
            &root.join("snapshots").join(format!("{snapshot_id}.json")),
            limits.max_metadata_bytes,
        )?;
        if sha256(&bytes) != snapshot_id {
            return Err(Error::new(
                "hash_mismatch",
                "snapshot hash does not match CURRENT",
            ));
        }
        let snapshot: Snapshot = serde_json::from_slice(&bytes)?;
        if snapshot.schema != "noetloom.state.v1"
            || snapshot.cells.len() > limits.max_cells
            || snapshot
                .parent
                .as_ref()
                .is_some_and(|value| !valid_digest(value))
            || (snapshot.generation == 0) != snapshot.parent.is_none()
        {
            return Err(Error::new(
                "invalid_store",
                "invalid snapshot schema, generation, or cell count",
            ));
        }
        for record in snapshot.cells.values() {
            if record.revision == 0
                || !valid_digest(&record.blob_sha256)
                || record.byte_len == 0
                || record.byte_len > limits.max_blob_bytes
                || record.value_bytes == 0
                || record.value_bytes > limits.max_blob_bytes
            {
                return Err(Error::new("invalid_store", "invalid cell record"));
            }
        }
        Ok(Self {
            root,
            limits,
            snapshot_id,
            snapshot,
            metadata_bytes_read: 65 + bytes.len() as u64,
        })
    }

    pub fn snapshot_id(&self) -> &str {
        &self.snapshot_id
    }

    pub fn cell_ref(&self, id: u64) -> Option<CellRef> {
        self.snapshot.cells.get(&id).map(|record| CellRef {
            id,
            revision: record.revision,
        })
    }

    pub fn transaction(&self) -> Transaction<'_> {
        Transaction {
            store: self,
            staged: BTreeMap::new(),
            staged_bytes: 0,
            reads: ReadMetrics::default(),
        }
    }
}

impl Transaction<'_> {
    fn revision(&self, id: u64) -> Option<u64> {
        self.staged
            .get(&id)
            .map(|value| value.revision)
            .or_else(|| {
                self.store
                    .snapshot
                    .cells
                    .get(&id)
                    .map(|record| record.revision)
            })
    }

    pub fn read_admission(&self, reference: CellRef) -> Result<ReadAdmission> {
        reference.validate()?;
        if self.revision(reference.id) != Some(reference.revision) {
            return Err(Error::new(
                "stale_reference",
                "cell does not exist at the requested transaction revision",
            ));
        }
        if let Some(value) = self.staged.get(&reference.id) {
            return Ok(ReadAdmission {
                payload_bytes: 0,
                value_bytes: value.value.logical_bytes()?,
            });
        }
        let record = &self.store.snapshot.cells[&reference.id];
        Ok(ReadAdmission {
            payload_bytes: record.byte_len,
            value_bytes: record.value_bytes,
        })
    }

    pub fn read(&mut self, reference: CellRef) -> Result<Value> {
        let admission = self.read_admission(reference)?;
        if let Some(value) = self.staged.get(&reference.id) {
            return Ok(value.value.clone());
        }
        let record = &self.store.snapshot.cells[&reference.id];
        let bytes = read_bounded(
            &self
                .store
                .root
                .join("blobs")
                .join(format!("{}.json", record.blob_sha256)),
            record.byte_len,
        )?;
        // Count actual successful file reads even if integrity validation subsequently fails.
        self.reads.payload_reads += 1;
        self.reads.payload_bytes += bytes.len() as u64;
        if bytes.len() as u64 != admission.payload_bytes || sha256(&bytes) != record.blob_sha256 {
            return Err(Error::new(
                "hash_mismatch",
                "activated payload failed length/hash verification",
            ));
        }
        let value: Value = serde_json::from_slice(&bytes)?;
        value.validate(self.store.limits.max_blob_bytes)?;
        if value.logical_bytes()? != admission.value_bytes {
            return Err(Error::new(
                "invalid_store",
                "payload and index disagree on logical size",
            ));
        }
        Ok(value)
    }

    pub fn staged_bytes(&self) -> u64 {
        self.staged_bytes
    }
    pub fn read_metrics(&self) -> &ReadMetrics {
        &self.reads
    }

    /// A None expectation creates a new cell; Some must match its latest transaction revision.
    pub fn write(
        &mut self,
        id: u64,
        expected: Option<u64>,
        value: Value,
        max_staged_bytes: u64,
    ) -> Result<CellRef> {
        if self.revision(id) != expected {
            return Err(Error::new(
                "write_conflict",
                "write expectation does not match transaction revision",
            ));
        }
        let revision = expected
            .unwrap_or(0)
            .checked_add(1)
            .ok_or_else(|| Error::new("write_conflict", "revision exhausted"))?;
        value.validate(self.store.limits.max_blob_bytes)?;
        let encoded = serde_json::to_vec(&value)?;
        if encoded.len() as u64 > self.store.limits.max_blob_bytes {
            return Err(Error::new(
                "store_budget",
                "serialized value exceeds blob budget",
            ));
        }
        let previous = self
            .staged
            .get(&id)
            .map_or(0, |value| value.encoded.len() as u64);
        let next_bytes = self
            .staged_bytes
            .checked_sub(previous)
            .and_then(|count| count.checked_add(encoded.len() as u64))
            .ok_or_else(|| Error::new("store_budget", "staged size overflow"))?;
        if next_bytes > max_staged_bytes || next_bytes > self.store.limits.max_store_bytes {
            return Err(Error::new("store_budget", "staged writes exceed budget"));
        }
        let new_cells = self
            .staged
            .keys()
            .filter(|key| !self.store.snapshot.cells.contains_key(key))
            .count();
        if expected.is_none()
            && self.store.snapshot.cells.len() + new_cells >= self.store.limits.max_cells
        {
            return Err(Error::new("store_budget", "cell count exceeds budget"));
        }
        self.staged.insert(
            id,
            Staged {
                revision,
                value,
                encoded,
            },
        );
        self.staged_bytes = next_bytes;
        Ok(CellRef { id, revision })
    }

    pub fn commit(self) -> Result<CommitReceipt> {
        let limit = self.store.limits.max_commit_validation_bytes;
        self.commit_with_validation_limit(limit)
    }

    pub fn commit_with_validation_limit(self, max_validation_bytes: u64) -> Result<CommitReceipt> {
        let store = self.store;
        let lock_path = store.root.join("WRITER.lock");
        if !fs::symlink_metadata(&lock_path)?.file_type().is_file() {
            return Err(Error::new(
                "invalid_store",
                "writer lock is not a regular file",
            ));
        }
        let lock = OpenOptions::new().read(true).write(true).open(lock_path)?;
        lock.try_lock()
            .map_err(|error| Error::new("writer_busy", error.to_string()))?;
        if current(&store.root)? != store.snapshot_id {
            return Err(Error::new(
                "write_conflict",
                "another transaction advanced CURRENT; reopen before retrying",
            ));
        }
        if self.staged.is_empty() {
            return Ok(CommitReceipt {
                before: store.snapshot_id.clone(),
                after: store.snapshot_id.clone(),
                generation: store.snapshot.generation,
                changed_cells: vec![],
                new_file_bytes: 0,
                validation_reads: 0,
                validation_bytes: 0,
                reads: self.reads,
            });
        }
        let mut snapshot = store.snapshot.clone();
        snapshot.generation = snapshot
            .generation
            .checked_add(1)
            .ok_or_else(|| Error::new("invalid_store", "generation exhausted"))?;
        snapshot.parent = Some(store.snapshot_id.clone());
        let mut files = BTreeMap::new();
        let mut changed_cells = Vec::new();
        for (id, staged) in self.staged {
            let digest = sha256(&staged.encoded);
            snapshot.cells.insert(
                id,
                CellRecord {
                    revision: staged.revision,
                    blob_sha256: digest.clone(),
                    byte_len: staged.encoded.len() as u64,
                    value_bytes: staged.value.logical_bytes()?,
                },
            );
            files.insert(
                store.root.join("blobs").join(format!("{digest}.json")),
                staged.encoded,
            );
            changed_cells.push(CellRef {
                id,
                revision: staged.revision,
            });
        }
        let bytes = serde_json::to_vec(&snapshot)?;
        if bytes.len() as u64 > store.limits.max_metadata_bytes {
            return Err(Error::new(
                "store_budget",
                "snapshot exceeds metadata budget",
            ));
        }
        let digest = sha256(&bytes);
        files.insert(
            store.root.join("snapshots").join(format!("{digest}.json")),
            bytes,
        );
        // Reserve all proposed files conservatively, even when some are deduplicated.
        let reserved = files
            .values()
            .try_fold(65_u64, |total, bytes| total.checked_add(bytes.len() as u64))
            .ok_or_else(|| Error::new("store_budget", "commit size overflow"))?;
        if store_bytes(&store.root)?
            .checked_add(reserved)
            .is_none_or(|size| size > store.limits.max_store_bytes)
        {
            return Err(Error::new(
                "store_budget",
                "commit plus retained history exceeds store budget",
            ));
        }
        let mut validation_reads = 0;
        let mut validation_bytes = 0_u64;
        for (path, bytes) in &files {
            if path.try_exists()? {
                validation_reads += 1;
                validation_bytes = validation_bytes
                    .checked_add(bytes.len() as u64)
                    .ok_or_else(|| Error::new("store_budget", "commit validation size overflow"))?;
            }
        }
        if validation_bytes > max_validation_bytes.min(store.limits.max_commit_validation_bytes) {
            return Err(Error::new(
                "store_budget",
                "immutable-file validation reads exceed commit I/O budget",
            ));
        }
        let mut new_file_bytes = 0;
        for (path, bytes) in files {
            new_file_bytes += immutable_file(&path, &bytes)?;
        }
        sync_directory(&store.root.join("blobs"))?;
        sync_directory(&store.root.join("snapshots"))?;
        let sequence = TEMP_SEQUENCE.fetch_add(1, Ordering::Relaxed);
        let pointer = store
            .root
            .join(format!(".CURRENT-{}-{sequence}", std::process::id()));
        create_file(&pointer, format!("{digest}\n").as_bytes())?;
        fs::rename(&pointer, store.root.join("CURRENT"))?;
        // After rename the commit is visible; do not misreport a rollback on sync failure.
        sync_directory(&store.root).map_err(|error| {
            Error::new(
                "commit_durability_uncertain",
                format!("CURRENT advanced to {digest}, but directory sync failed: {error}"),
            )
        })?;
        Ok(CommitReceipt {
            before: store.snapshot_id.clone(),
            after: digest,
            generation: snapshot.generation,
            changed_cells,
            new_file_bytes: new_file_bytes + 65,
            validation_reads,
            validation_bytes,
            reads: self.reads,
        })
    }
}
