"use client";

/*
 * IndexedDB wrapper for Nova's offline support
 * (OFFLINE_ARCHITECTURE_BRAIN_TRUST_2026-08-16.md section F).
 *
 * Phase 1 stores (prospects, salesKits) are keyed by a stable id and carry a
 * `syncedAt` ISO-8601 timestamp on every record -- Celestina's finding C is
 * binding on this whole design: every view sourced from this store must
 * show a "cached as of [timestamp]" badge, never presented as a live
 * number. Phase 2 adds a third store, the sync outbox, for queued
 * customization edits (one note field, one gap-selection array, nothing
 * heavier -- the Amaya-scoped definition of "customize" both reviews use).
 *
 * Raw IndexedDB, no library: three small object stores don't justify a new
 * npm dependency, and this repo had zero client-side persistence anywhere
 * before Phase 1.
 */

export type CachedProspect = {
  id: string;
  business_name: string;
  contact_name?: string | null;
  contact_email?: string | null;
  city?: string | null;
  current_score?: number | null;
  agent_id: string;
  created_at?: string;
  syncedAt: string; // when THIS device last pulled it, not when the row was created
};

export type CachedSalesKit = {
  prospectId: string;
  url: string;
  businessName: string;
  html: string;
  syncedAt: string;
};

/** A queued customization edit, not yet confirmed synced. `id` is
 * client-generated (crypto.randomUUID()) and doubles as the natural
 * idempotency key -- a retried drain after a partial failure re-PUTs the
 * same id, never creates a duplicate outbox entry. `clientTimestamp` is
 * what the backend's last-write-wins comparison actually keys on. */
export type OutboxEntry = {
  id: string;
  prospectId: string;
  note: string;
  selectedGapIndices: number[];
  clientTimestamp: string;
  status: "pending" | "synced" | "failed";
  createdAt: string;
  lastError?: string;
};

const DB_NAME = "nova-field-offline";
const DB_VERSION = 2;
const PROSPECTS_STORE = "prospects";
const KITS_STORE = "salesKits";
const OUTBOX_STORE = "outbox";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB is not available in this environment."));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(PROSPECTS_STORE)) {
        db.createObjectStore(PROSPECTS_STORE, { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains(KITS_STORE)) {
        db.createObjectStore(KITS_STORE, { keyPath: "prospectId" });
      }
      if (!db.objectStoreNames.contains(OUTBOX_STORE)) {
        db.createObjectStore(OUTBOX_STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("Failed to open nova-field-offline"));
  });
}

export async function putProspects(prospects: CachedProspect[]): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(PROSPECTS_STORE, "readwrite");
    const store = tx.objectStore(PROSPECTS_STORE);
    for (const p of prospects) store.put(p);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error ?? new Error("Failed to write cached prospects"));
    };
  });
}

export async function getAllCachedProspects(): Promise<CachedProspect[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(PROSPECTS_STORE, "readonly");
    const store = tx.objectStore(PROSPECTS_STORE);
    const req = store.getAll();
    req.onsuccess = () => {
      db.close();
      resolve((req.result as CachedProspect[]) || []);
    };
    req.onerror = () => {
      db.close();
      reject(req.error ?? new Error("Failed to read cached prospects"));
    };
  });
}

export async function putSalesKit(kit: CachedSalesKit): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(KITS_STORE, "readwrite");
    tx.objectStore(KITS_STORE).put(kit);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error ?? new Error("Failed to write cached sales kit"));
    };
  });
}

export async function getCachedSalesKit(prospectId: string): Promise<CachedSalesKit | undefined> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(KITS_STORE, "readonly");
    const req = tx.objectStore(KITS_STORE).get(prospectId);
    req.onsuccess = () => {
      db.close();
      resolve(req.result as CachedSalesKit | undefined);
    };
    req.onerror = () => {
      db.close();
      reject(req.error ?? new Error("Failed to read cached sales kit"));
    };
  });
}

export async function clearOfflineStore(): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction([PROSPECTS_STORE, KITS_STORE, OUTBOX_STORE], "readwrite");
    tx.objectStore(PROSPECTS_STORE).clear();
    tx.objectStore(KITS_STORE).clear();
    tx.objectStore(OUTBOX_STORE).clear();
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error ?? new Error("Failed to clear offline store"));
    };
  });
}

// --- Outbox (Phase 2, write-side offline) -----------------------------------

/** Queue a customization edit. Works offline by construction -- this only
 * ever touches IndexedDB, never the network. Overwrites any existing
 * pending entry for the SAME prospect (not append) — a second edit to the
 * same prospect before the first synced should replace it, not queue two
 * writes that would just resolve by timestamp anyway. */
export async function queueOutboxEntry(entry: Omit<OutboxEntry, "id" | "status" | "createdAt"> & { id?: string }): Promise<OutboxEntry> {
  const existing = await getAllOutboxEntries();
  const priorForSameProspect = existing.find((e) => e.prospectId === entry.prospectId && e.status !== "synced");
  const record: OutboxEntry = {
    id: priorForSameProspect?.id ?? entry.id ?? (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `${entry.prospectId}-${Date.now()}`),
    prospectId: entry.prospectId,
    note: entry.note,
    selectedGapIndices: entry.selectedGapIndices,
    clientTimestamp: entry.clientTimestamp,
    status: "pending",
    createdAt: priorForSameProspect?.createdAt ?? new Date().toISOString(),
  };
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(OUTBOX_STORE, "readwrite");
    tx.objectStore(OUTBOX_STORE).put(record);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error ?? new Error("Failed to queue outbox entry"));
    };
  });
  return record;
}

export async function getAllOutboxEntries(): Promise<OutboxEntry[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(OUTBOX_STORE, "readonly");
    const req = tx.objectStore(OUTBOX_STORE).getAll();
    req.onsuccess = () => {
      db.close();
      resolve((req.result as OutboxEntry[]) || []);
    };
    req.onerror = () => {
      db.close();
      reject(req.error ?? new Error("Failed to read outbox"));
    };
  });
}

export async function getPendingOutboxCount(): Promise<number> {
  const entries = await getAllOutboxEntries();
  return entries.filter((e) => e.status === "pending" || e.status === "failed").length;
}

/** Mark an entry synced and remove it -- a synced entry carries no
 * further meaning once the server has it; keeping it around risks a
 * confusing double-apply if the outbox is ever replayed wholesale. */
export async function markOutboxSynced(id: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(OUTBOX_STORE, "readwrite");
    tx.objectStore(OUTBOX_STORE).delete(id);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error ?? new Error("Failed to clear synced outbox entry"));
    };
  });
}

export async function markOutboxFailed(id: string, error: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(OUTBOX_STORE, "readwrite");
    const store = tx.objectStore(OUTBOX_STORE);
    const req = store.get(id);
    req.onsuccess = () => {
      const record = req.result as OutboxEntry | undefined;
      if (record) {
        record.status = "failed";
        record.lastError = error;
        store.put(record);
      }
    };
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error ?? new Error("Failed to mark outbox entry failed"));
    };
  });
}
