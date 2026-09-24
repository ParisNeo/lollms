"""
Example demonstrating the Shared Sentence Transformer Vectorizer.

In multi-user or multi-process server applications (e.g. FastAPI/Uvicorn, Celery,
or microservices), loading separate SentenceTransformer models in each process
leads to excessive VRAM/RAM consumption and Out-Of-Memory (OOM) errors.

SafeStore solves this with a Shared Model Server:
1. First instance automatically spawns a background model server daemon.
2. Subsequent instances and processes connect to the same server (1x model memory!).
3. Dynamic Micro-Batching: Concurrent vectorization requests across multiple clients
   are automatically grouped into batched inference passes for high GPU efficiency.
4. Persistent Lifecycle: The server stays alive until explicitly instructed to die
   via a special shutdown command (`SafeStore.shutdown_shared_vectorizer()`).
"""

import os
import sys
import time
import socket
import multiprocessing
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed


def disable_broken_torchvision() -> None:
    """
    Guards against PyTorch/torchvision binary mismatches where an incompatible
    torchvision build causes: RuntimeError: operator torchvision::nms does not exist.
    """
    for mod in list(sys.modules.keys()):
        if mod == "torchvision" or mod.startswith("torchvision."):
            try:
                del sys.modules[mod]
            except KeyError:
                pass
    sys.modules["torchvision"] = None
    sys.modules["torchvision.ops"] = None


disable_broken_torchvision()

import safe_store
from safe_store import SafeStore, LogLevel, shutdown_shared_vectorizer


def check_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def cleanup_db_files(db_file: str):
    db_path = Path(db_file)
    for p in [db_path, Path(f"{db_path}.lock"), Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]:
        p.unlink(missing_ok=True)


def worker_process(
    process_id: int,
    db_path: str,
    port: int,
    model_name: str
) -> dict:
    """
    Worker process representing an independent user or API worker.
    Connects to the shared background model server, taking advantage of
    shared memory and dynamic micro-batching.
    """
    disable_broken_torchvision()

    try:
        print(f"  [Worker {process_id}] Starting and connecting to shared server on port {port}...", flush=True)

        store = SafeStore(
            db_path=db_path,
            vectorizer_name="st",
            vectorizer_config={
                "model_name": model_name,
                "use_shared_server": True,
                "port": port,
                "idle_timeout": 0.0  # Stay alive until explicit shutdown command
            },
            log_level=LogLevel.WARNING
        )

        with store:
            doc_text = f"""
            # Worker {process_id} Technical Briefing
            
            This document is generated concurrently by worker process {process_id}.
            It demonstrates zero-duplicate VRAM allocation and dynamic request batching.
            Worker identity tag: WORKER_CONCURRENCY_{process_id}.
            """

            store.add_text(
                unique_id=f"doc_worker_{process_id}.md",
                text=doc_text,
                metadata={"worker_id": process_id, "type": "shared_model_test"}
            )

            results = store.query(f"WORKER_CONCURRENCY_{process_id}", top_k=1)
            
            if not results:
                return {"process_id": process_id, "status": "error", "message": "No results found"}
            
            top_result = results[0]
            expected_doc = f"doc_worker_{process_id}.md"
            actual_doc = Path(top_result["file_path"]).name
            
            print(f"  [Worker {process_id}] Query succeeded! Top match: '{actual_doc}'", flush=True)

            return {
                "process_id": process_id,
                "status": "success",
                "found_doc": actual_doc,
                "is_correct_doc": actual_doc == expected_doc,
                "similarity": top_result["similarity_percent"]
            }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"  [Worker {process_id}] Exception:\n{tb}", flush=True)
        return {"process_id": process_id, "status": "error", "message": str(e)}


def main():
    print("=" * 70, flush=True)
    print(" SafeStore Multi-User / Multi-Process Shared Vectorizer Demo ", flush=True)
    print("=" * 70, flush=True)

    db_file = "shared_vectorizer_test.db"
    port = 8769
    model_name = "all-MiniLM-L6-v2"
    num_workers = 3

    # Step 0: Free port if previously bound
    cleanup_db_files(db_file)
    if check_port_in_use(port):
        print(f"[*] Port {port} is in use. Sending shutdown command to free it...", flush=True)
        shutdown_shared_vectorizer(port=port)
        time.sleep(1.0)

    # Step 1: Initialize server via instance 0
    print("\n[Step 1] Initializing instance 0 (spawns background daemon)...", flush=True)
    res_0 = worker_process(0, db_file, port, model_name)
    if res_0["status"] != "success":
        print(f"[!] Instance 0 failed: {res_0.get('message')}", flush=True)
        return

    print("✓ Instance 0 successfully launched and connected to the shared server!", flush=True)

    # Step 2: Spawn concurrent workers (they connect to existing daemon with 0x duplicate VRAM)
    print(f"\n[Step 2] Spawning {num_workers} parallel workers concurrently...", flush=True)
    print("• All workers share the same single model in memory/VRAM.", flush=True)
    print("• Concurrent requests are dynamically micro-batched by the server.\n", flush=True)

    start_time = time.time()
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(worker_process, i + 1, db_file, port, model_name)
            for i in range(num_workers)
        ]

        results = []
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            if res["status"] == "success":
                print(f"  ✓ Worker {res['process_id']} completed: Found '{res['found_doc']}' (Score: {res['similarity']:.1f}%)", flush=True)
            else:
                print(f"  ✗ Worker {res['process_id']} failed: {res.get('message')}", flush=True)

    elapsed = time.time() - start_time
    print(f"\nAll parallel workers finished in {elapsed:.2f} seconds.", flush=True)

    # Step 3: Verify server persistence
    print("\n[Step 3] Verifying Server Persistence:", flush=True)
    server_alive = check_port_in_use(port)
    if server_alive:
        print(f"  ✓ Confirmed: Shared model server on port {port} remains alive for future requests.", flush=True)
    else:
        print(f"  ✗ Server unexpectedly stopped.", flush=True)

    # Step 4: Special command to die (shutdown)
    print("\n[Step 4] Issuing the Special Command to Die (Shutdown):", flush=True)
    print("Calling `SafeStore.shutdown_shared_vectorizer(port=...)`...", flush=True)
    stopped = SafeStore.shutdown_shared_vectorizer(port=port)
    time.sleep(1.0)

    is_down = not check_port_in_use(port)
    if is_down and stopped:
        print("  ✓ Special shutdown command executed successfully! Server daemon terminated.", flush=True)
    else:
        print(f"  Shutdown result: {stopped}, Port still listening: {check_port_in_use(port)}", flush=True)

    # Cleanup test files
    cleanup_db_files(db_file)
    print("\n" + "=" * 70, flush=True)
    print(" Shared Vectorizer Demo Complete ", flush=True)
    print("=" * 70 + "\n", flush=True)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()