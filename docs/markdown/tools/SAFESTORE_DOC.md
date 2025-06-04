# safe_store Documentation
*(Version: 1.5.0, Generated: 2025-05-08 09:17:23)*

## Table of Contents

1.  [Introduction](#1-introduction)
    *   [What is safe\_store?](#what-is-safe_store)
    *   [Why use safe\_store?](#why-use-safe_store)
    *   [Key Features](#key-features)
    *   [Architecture Overview](#architecture-overview)
2.  [Installation](#2-installation)
    *   [Basic Installation](#basic-installation)
    *   [Optional Dependencies](#optional-dependencies)
    *   [Development Installation](#development-installation)
3.  [Quick Start](#3-quick-start)
4.  [Core Concepts](#4-core-concepts)
    *   [4.1. The `safe_store` Instance](#41-the-safe_store-instance)
    *   [4.2. Document Indexing (`add_document`)](#42-document-indexing-add_document)
    *   [4.3. Vectorization](#43-vectorization)
    *   [4.4. Querying (`query`)](#44-querying-query)
    *   [4.5. Encryption](#45-encryption)
    *   [4.6. Concurrency](#46-concurrency)
    *   [4.7. Logging](#47-logging)
    *   [4.8. Managing the Store](#48-managing-the-store)
5.  [API Reference](#5-api-reference)
    *   [`safe_store.safe_store`](#safe_storesafe_store_1)
    *   [`safe_store.LogLevel`](#safe_storeloglevel)
    *   [Exceptions](#exceptions)
6.  [Examples](#6-examples)
7.  [Error Handling](#7-error-handling)
8.  [Future Work](#8-future-work)
9.  [Contributing](#9-contributing)
10. [Changelog](#10-changelog)
11. [License](#11-license)

## 1. Introduction

### What is safe_store?

**safe\_store** is a Python library providing a lightweight, file-based vector database using SQLite. It's designed for simplicity and efficiency, making it ideal for integrating into local Retrieval-Augmented Generation (RAG) pipelines. It allows you to store, manage, and query document embeddings locally with features like automatic change detection, support for multiple vectorization methods, safe concurrent access, various document parsers, and optional encryption at rest.

### Why use safe_store?

*   **🎯 RAG Focused:** Built with local RAG use cases as a primary goal.
*   **🚀 Simple & Lightweight:** Uses a single SQLite file – no heavy dependencies or external database servers.
*   **🏠 Local First:** Keep your embeddings and document text entirely on your local machine or network share.
*   **🤝 Concurrent Safe:** Handles database writes from multiple processes safely.
*   **🧠 Multiple Vectorizers:** Index with different embedding models (Sentence Transformers, TF-IDF) side-by-side.
*   **📄 Document Parsing:** Built-in support for `.txt`, `.pdf`, `.docx`, and `.html`.
*   **🔒 Optional Encryption:** Encrypts document chunk text at rest for enhanced security.
*   **🔄 Change Aware:** Automatically detects file changes and re-indexes efficiently.
*   **🗣️ Informative Logging:** Clear, leveled, and colorful console feedback via `ascii_colors`.

### Key Features

*   **Storage:** All data (documents, chunks, vectors, metadata) stored in a single SQLite file (`.db`).
*   **Concurrency:** Process-safe writes using file-based locking (`filelock`). Concurrent reads enabled by SQLite's WAL mode.
*   **Indexing (`add_document`):**
    *   Parses `.txt`, `.pdf`, `.docx`, `.html`/`.htm` files (requires `safe_store[parsing]`).
    *   Stores full original text.
    *   Configurable character-based chunking with overlap.
    *   Calculates file hash (SHA256) for change detection; re-indexes if content changes.
    *   Associates optional JSON metadata with documents.
*   **Encryption (Optional):**
    *   Encrypts `chunk_text` at rest using Fernet (AES-128-CBC + HMAC) via `cryptography`.
    *   Enabled by providing an `encryption_key` during `safe_store` initialization.
    *   Automatic decryption during queries if the correct key is provided.
*   **Vectorization:**
    *   Supports multiple vectorization methods simultaneously.
    *   **Sentence Transformers:** Integrates `sentence-transformers` models (e.g., `st:all-MiniLM-L6-v2`).
    *   **TF-IDF:** Integrates `scikit-learn`'s `TfidfVectorizer`. Handles fitting and stores state.
*   **Querying (`query`):**
    *   Finds `top_k` chunks based on cosine similarity.
    *   Specify which `vectorizer_name` to use.
*   **Management Methods:**
    *   `add_vectorization()`: Adds embeddings for a new method to existing documents.
    *   `remove_vectorization()`: Deletes a vectorization method and its vectors.
    *   `list_documents()`: Retrieves metadata about stored documents.
    *   `list_vectorization_methods()`: Retrieves details about registered vectorizers.
    *   `list_possible_vectorizer_names()`: Provides example vectorizer names.
*   **Logging:** Rich console logging via `ascii_colors`, configurable.

### Architecture Overview

`safe_store` is built around a central SQLite database file. Key components include:

*   **`safe_store` Class:** The main entry point for interacting with the library.
*   **Core (`safe_store.core`):**
    *   `db.py`: Handles SQLite connection, schema initialization, and low-level CRUD operations.
    *   `exceptions.py`: Defines custom exceptions.
*   **Indexing (`safe_store.indexing`):**
    *   `parser.py`: Logic for parsing different document file types.
    *   `chunking.py`: Text splitting logic.
*   **Vectorization (`safe_store.vectorization`):**
    *   `manager.py`: Manages different vectorizer instances and their database records.
    *   `methods/`: Implementations for specific vectorizers (Sentence Transformers, TF-IDF).
*   **Search (`safe_store.search`):**
    *   `similarity.py`: Cosine similarity calculation.
*   **Security (`safe_store.security`):**
    *   `encryption.py`: Handles encryption and decryption of chunk text.
*   **Utils (`safe_store.utils`):**
    *   `concurrency.py` (conceptual, as `filelock` is used directly in `store.py`): Manages locking.

All data, including document text, chunked text (potentially encrypted), metadata, vectorizer configurations (like TF-IDF vocabulary), and the vector embeddings themselves, are stored within the SQLite database.

## 2. Installation

### Basic Installation

You can install `safe_store` using pip:

```bash
pip install safe_store
```

This installs the core library with `numpy`, `ascii_colors`, and `filelock` as dependencies.

### Optional Dependencies

`safe_store` offers optional features that require additional dependencies. You can install them as "extras":

*   **Sentence Transformers Support:** For using embedding models from the `sentence-transformers` library.
    ```bash
    pip install safe_store[sentence-transformers]
    ```

*   **TF-IDF Support:** For using TF-IDF vectorization (requires `scikit-learn`).
    ```bash
    pip install safe_store[tfidf]
    ```

*   **Document Parsing Support:** For parsing `.pdf`, `.docx`, and `.html` files.
    This extra includes `pypdf`, `python-docx`, `beautifulsoup4`, and `lxml`.
    ```bash
    pip install safe_store[parsing]
    ```

*   **Encryption Support:** For encrypting chunk text at rest (requires `cryptography`).
    ```bash
    pip install safe_store[encryption]
    ```

*   **Install All Extras:** To install all optional features:
    ```bash
    pip install safe_store[all]
    ```

You can also install specific combinations, for example:
```bash
pip install safe_store[sentence-transformers,parsing,encryption]
```

### Development Installation

If you plan to contribute to `safe_store`, you can install it in editable mode along with development dependencies (for testing, linting, building):

```bash
git clone https://github.com/ParisNeo/safe_store.git
cd safe_store
pip install -e .[dev]
```
This typically includes `pytest`, `flake8`/`ruff`, `black`, `mypy`, and Sphinx for documentation.

## 3. Quick Start

This example demonstrates the basic workflow: initializing the store, adding documents with Sentence Transformer embeddings, and querying.

```python
import safe_store
from pathlib import Path
import shutil # For cleanup

# --- 0. Configuration & Cleanup (Optional) ---
DB_FILE = "quickstart_store.db"
DOC_DIR = Path("temp_docs_quickstart")

if DOC_DIR.exists(): shutil.rmtree(DOC_DIR)
if Path(DB_FILE).exists(): Path(DB_FILE).unlink()
if Path(f"{DB_FILE}.lock").exists(): Path(f"{DB_FILE}.lock").unlink(missing_ok=True)
DOC_DIR.mkdir(exist_ok=True)

# --- 1. Prepare Sample Documents ---
doc1_path = DOC_DIR / "intro.txt"
doc1_content = """
safe_store is a Python library for local vector storage.
It uses SQLite as its backend, making it lightweight and file-based.
"""
doc1_path.write_text(doc1_content.strip(), encoding='utf-8')

doc2_path = DOC_DIR / "features.txt"
doc2_content = "Key features include concurrency control and support for multiple vectorizers."
doc2_path.write_text(doc2_content.strip(), encoding='utf-8')

print(f"Sample documents created in: {DOC_DIR.resolve()}")

# --- 2. Initialize safe_store ---
# Using INFO log level for less verbose output in this example.
# For no encryption, omit encryption_key or set to None.
# For this example, let's enable encryption.
# !! IN A REAL APP, MANAGE YOUR KEY SECURELY (e.g., env var, secrets manager) !!
my_secret_password = "a_very_secret_password_123!"

try:
    store = safe_store.SafeStore(
        db_path=DB_FILE,
        log_level=safe_store.LogLevel.INFO,
        encryption_key=my_secret_password # Enable encryption
    )
except safe_store.ConfigurationError as e:
    print(f"Initialization Error: {e}")
    print("Make sure you have 'cryptography' installed: pip install safe_store[encryption]")
    exit()


# --- 3. Use safe_store as a Context Manager (Recommended) ---
try:
    with store:
        # --- 3a. Add Documents ---
        # Chunk text will be encrypted because encryption_key was provided.
        print("\n--- Indexing Documents ---")
        store.add_document(
            doc1_path,
            vectorizer_name="st:all-MiniLM-L6-v2", # Default, but explicit
            chunk_size=80, # Smaller chunk size for small docs
            chunk_overlap=10,
            metadata={"source": "quickstart", "topic": "introduction"}
        )
        store.add_document(
            doc2_path,
            vectorizer_name="st:all-MiniLM-L6-v2",
            metadata={"source": "quickstart", "topic": "features"}
        )

        # --- 3b. Query the Store ---
        # Results will be automatically decrypted if the store has the correct key.
        print("\n--- Querying for 'vector database features' ---")
        query_text = "vector database features"
        results = store.query(
            query_text,
            vectorizer_name="st:all-MiniLM-L6-v2",
            top_k=2
        )

        if results:
            for i, res in enumerate(results):
                print(f"  Result {i+1}: Score={res['similarity']:.4f}")
                print(f"    File: '{Path(res['file_path']).name}'")
                print(f"    Text: '{res['chunk_text'][:100]}...'") # Decrypted text
                print(f"    Metadata: {res.get('metadata')}")
                # Verify decryption occurred
                if my_secret_password:
                    assert "[Encrypted" not in res['chunk_text'], "Text appears to be encrypted in results!"
        else:
            print("  No results found.")

except safe_store.ConfigurationError as e:
    print(f"\n[ERROR] Missing dependency: {e}")
    print("Please install required extras (e.g., pip install safe_store[sentence-transformers,encryption])")
except safe_store.ConcurrencyError as e:
    print(f"\n[ERROR] Lock timeout or concurrency issue: {e}")
except safe_store.EncryptionError as e:
    print(f"\n[ERROR] Encryption/Decryption issue: {e}")
except Exception as e:
    print(f"\n[ERROR] An unexpected error occurred: {e.__class__.__name__}: {e}")
finally:
    # Connection is closed automatically by the 'with' statement.
    print("\n--- Quick Start Example Finished ---")
    # Optional: Clean up created files
    # shutil.rmtree(DOC_DIR)
    # Path(DB_FILE).unlink(missing_ok=True)
    # Path(f"{DB_FILE}.lock").unlink(missing_ok=True)

```
*(For more detailed examples, see the `examples/` directory in the repository, including `basic_usage.py`, `custom_logging.py`, and `encryption_usage.py`.)*

## 4. Core Concepts

### 4.1. The `safe_store` Instance

The `safe_store.safe_store` class is the main entry point for all operations.

#### Initialization

You create an instance of the store by providing a path to the SQLite database file. If the file doesn't exist, it will be created.

```python
import safe_store

# Initialize with default settings (db at 'safe_store.db', INFO log level)
store = safe_store.SafeStore()

# Initialize with a custom database path and DEBUG logging
store_custom = safe_store.SafeStore(
    db_path="my_data/vector_store.db",
    log_level=safe_store.LogLevel.DEBUG
)

# Initialize with a lock timeout of 30 seconds
store_timeout = safe_store.SafeStore(lock_timeout=30)

# Initialize with encryption (see Encryption section for details)
# Requires `safe_store[encryption]` installed.
# !! MANAGE YOUR KEY SECURELY !!
encryption_password = "your-very-strong-password"
store_encrypted = safe_store.SafeStore(
    db_path="secure_store.db",
    encryption_key=encryption_password
)
```

**`__init__` Parameters:**

*   `db_path` (Union[str, Path], optional): Path to the SQLite database file. Defaults to `"safe_store.db"` in the current working directory.
*   `log_level` (safe_store.LogLevel, optional): Minimum log level for console output. Defaults to `LogLevel.INFO`. Other options: `LogLevel.DEBUG`, `LogLevel.WARNING`, `LogLevel.ERROR`, `LogLevel.CRITICAL`, `LogLevel.SUCCESS`.
*   `lock_timeout` (int, optional): Timeout in seconds for acquiring the inter-process write lock. Defaults to 60 seconds. A value of `0` or negative means non-blocking (will raise `ConcurrencyError` immediately if lock is held).
*   `encryption_key` (Optional[str], optional): A password string used to derive an encryption key for encrypting chunk text at rest. If `None` (default), encryption is disabled. If provided, `cryptography` must be installed (`safe_store[encryption]`).

#### Context Manager Usage

It is highly recommended to use the `safe_store` instance as a context manager (`with ... as ...`). This ensures that the database connection is properly opened at the start and closed at the end, even if errors occur.

```python
try:
    with safe_store.SafeStore("my_store.db") as store:
        # Perform operations like store.add_document(...), store.query(...)
        pass
except Exception as e:
    print(f"An error occurred: {e}")
# Connection is automatically closed when exiting the 'with' block
```

#### Closing the Store

If you don't use the context manager, you must manually close the store connection using the `close()` method to release resources and ensure data is flushed.

```python
store = safe_store.SafeStore("my_store.db")
try:
    # ... perform operations ...
    pass
finally:
    store.close()
```

### 4.2. Document Indexing (`add_document`)

The `add_document` method is the primary way to ingest documents into `safe_store`. It orchestrates several steps:

1.  **File Hashing:** Calculates the SHA256 hash of the file's content.
2.  **Change Detection:** Compares the current hash with a stored hash (if the document was previously indexed).
    *   If `force_reindex` is `False` and the hash matches an existing document for which the specified `vectorizer_name` vectors already exist, the process is skipped for efficiency.
    *   If the hash has changed or `force_reindex` is `True`, old chunks and vectors for that document are removed.
3.  **Parsing:** Extracts text content from the file based on its extension.
4.  **Chunking:** Splits the extracted text into smaller, potentially overlapping, chunks.
5.  **Encryption (if enabled):** Encrypts each chunk's text before storing it in the database.
6.  **Storage:** Saves the document metadata, full text, and chunk information (text, position, encryption status) to the database.
7.  **Vectorization:** Generates vector embeddings for each chunk using the specified `vectorizer_name`. If the vectorizer is TF-IDF and not yet fitted, it will be fitted *only* on the chunks of the current document.
8.  **Vector Storage:** Saves the generated vectors to the database, linked to their respective chunks and the vectorization method.

```python
with safe_store.SafeStore("library.db") as store:
    store.add_document(
        file_path="path/to/my_document.pdf",
        vectorizer_name="st:all-MiniLM-L6-v2", # Or your preferred vectorizer
        chunk_size=1500,
        chunk_overlap=200,
        metadata={"category": "research", "year": 2024},
        force_reindex=False, # Only re-index if file content changed
        # vectorizer_params for TF-IDF might be: {'ngram_range': (1,2), 'max_features': 5000}
    )
```

#### Supported File Types and Parsing

`safe_store` can parse the following file types by default if the corresponding optional dependencies are installed (`safe_store[parsing]`):

*   `.txt`: Plain text files (UTF-8 encoding assumed).
*   `.pdf`: PDF documents (uses `pypdf`).
*   `.docx`: Microsoft Word documents (uses `python-docx`).
*   `.html`, `.htm`: HTML files (uses `BeautifulSoup4` with `lxml` if available, else `html.parser`).

If you attempt to add a document of an unsupported type or if the required parsing library is not installed, a `ConfigurationError` or `ParsingError` will be raised.

#### Text Chunking

Text is split into chunks to make vectorization and similarity search more granular and effective.
*   `chunk_size` (int): The target maximum size of each chunk in characters (default: 1000).
*   `chunk_overlap` (int): The number of characters to overlap between consecutive chunks (default: 150). This helps maintain context across chunk boundaries. `chunk_overlap` must be less than `chunk_size`.

#### File Change Detection & Re-indexing

`safe_store` uses SHA256 hashing to detect if a file's content has changed since it was last indexed.
*   **Unchanged File:** If `add_document` is called on a file whose content hasn't changed (hash matches) and vectors for the specified `vectorizer_name` already exist, `safe_store` skips re-processing to save time.
*   **Changed File:** If the content has changed, `safe_store` automatically removes the old document's chunks and vectors and re-indexes the new content.
*   **`force_reindex=True`:** This flag forces `safe_store` to re-process the document (parse, chunk, vectorize) even if its content hash hasn't changed. Useful if you've changed chunking parameters or want to ensure fresh processing.

#### Storing Metadata

You can associate a dictionary of custom metadata with each document. This metadata must be JSON serializable.

```python
store.add_document(
    "report.txt",
    metadata={"author": "Jane Doe", "version": 2.1, "tags": ["finance", "q3"]}
)
```
Metadata is returned with query results and when listing documents.

### 4.3. Vectorization

Vectorization is the process of converting text into numerical representations (embeddings) that capture semantic meaning. `safe_store` supports using multiple vectorization methods simultaneously.

#### Supported Vectorizer Types

##### 1. Sentence Transformers

*   **Naming Convention:** `st:<model_name_from_sentence_transformers_library>`
    *   Example: `st:all-MiniLM-L6-v2` (this is also the `safe_store.DEFAULT_VECTORIZER`)
    *   Example: `st:multi-qa-mpnet-base-dot-v1`
    *   You can use any model name that is loadable by the `sentence-transformers` Python library. Check the [Hugging Face Model Hub](https://huggingface.co/models?library=sentence-transformers) for available models.
*   **Requires:** `safe_store[sentence-transformers]` to be installed.
*   **How it works:** Uses pre-trained models to generate dense vector embeddings. These models are typically downloaded automatically by the `sentence-transformers` library on first use.

##### 2. TF-IDF (Term Frequency-Inverse Document Frequency)

*   **Naming Convention:** `tfidf:<your_custom_name>`
    *   Example: `tfidf:my_project_docs_ngram12`
    *   `<your_custom_name>` is an arbitrary string you choose to identify this specific TF-IDF configuration.
*   **Requires:** `safe_store[tfidf]` (which installs `scikit-learn`).
*   **How it works:** TF-IDF is a classical information retrieval technique that weighs words based on their frequency in a document and across the entire corpus.
*   **Fitting:** TF-IDF vectorizers **must be fitted** on a corpus of text to learn the vocabulary and IDF weights. `safe_store` handles this:
    *   **Local Fit (during `add_document`):** If you use a `tfidf:` vectorizer in `add_document` and it hasn't been fitted yet (or its name is new), it will be fitted *only* on the chunks of the *current document being added*. This is generally not recommended for good TF-IDF performance unless you are indexing a single, representative document.
    *   **Global/Targeted Fit (during `add_vectorization`):** This is the recommended way to fit a TF-IDF model. When you call `store.add_vectorization("tfidf:my_global_tfidf")`, if the model isn't fitted, `safe_store` will fetch all text chunks (or chunks from `target_doc_path` if specified) from the database, decrypt them if necessary, and fit the TF-IDF model on this broader corpus.
*   **Stored State:** The fitted TF-IDF model's vocabulary, IDF weights, and original initialization parameters (e.g., `ngram_range`, `max_features`, `stop_words`) are stored in the database. This allows the model to be reloaded and used consistently.
*   **`vectorizer_params`:** When first introducing a TF-IDF vectorizer (either via `add_document` or `add_vectorization`), you can pass scikit-learn specific parameters using the `vectorizer_params` argument:
    ```python
    store.add_document(
        "doc.txt",
        vectorizer_name="tfidf:custom_config",
        vectorizer_params={
            "ngram_range": (1, 2), # Use unigrams and bigrams
            "max_features": 10000,  # Limit vocabulary size
            "stop_words": "english"
            # other sklearn.feature_extraction.text.TfidfVectorizer params
        }
    )
    ```

#### Managing Vectorizations

*   **`add_vectorization(vectorizer_name, target_doc_path=None, vectorizer_params=None, batch_size=64)`**
    *   Adds embeddings for a *new* `vectorizer_name` to documents already in the store.
    *   Does **not** re-parse or re-chunk. It uses existing chunks.
    *   If `target_doc_path` is given, only that document's chunks are vectorized. Otherwise, all documents are processed.
    *   If `vectorizer_name` is a TF-IDF model that isn't fitted, it will be fitted on the selected corpus (all docs or `target_doc_path`'s chunks). Chunk text is decrypted if needed for fitting.
    *   Useful for:
        *   Adding embeddings from a new Sentence Transformer model.
        *   Adding a new TF-IDF variant, possibly fitted on the entire corpus.
    ```python
    # After indexing some documents with an ST model...
    # Add a new TF-IDF vectorization, fitting it on all documents
    store.add_vectorization(
        "tfidf:global_content_model",
        vectorizer_params={"stop_words": "english", "min_df": 5}
    )
    ```

*   **`remove_vectorization(vectorizer_name)`**
    *   Deletes a vectorization method and all its associated vector embeddings from the database.
    *   The document text and chunks remain.
    ```python
    store.remove_vectorization("tfidf:old_model_to_remove")
    ```

*   **`list_vectorization_methods()`**
    *   Returns a list of dictionaries, each describing a registered vectorization method (name, type, dimension, parameters).
    ```python
    methods = store.list_vectorization_methods()
    for method in methods:
        print(f"- Name: {method['method_name']}, Type: {method['method_type']}, Dim: {method['vector_dim']}")
        if method['method_type'] == 'tfidf':
            print(f"  Fitted: {method.get('params', {}).get('fitted', False)}")
    ```

*   **`safe_store.list_possible_vectorizer_names()` (Static Method)**
    *   Provides a list of example and common vectorizer names to help you get started.
    *   This list is not exhaustive. For Sentence Transformers, any model from the `sentence-transformers` library hub can be used with the `st:` prefix. For TF-IDF, the name after `tfidf:` is user-defined.
    ```python
    suggestions = safe_store.safe_store.list_possible_vectorizer_names()
    for suggestion in suggestions:
        print(suggestion)
    ```
    Example Output:
    ```
    --- Sentence Transformers ('st:') ---
    st:all-MiniLM-L6-v2
    st:all-mpnet-base-v2
    ...
    Info: Use any model name from huggingface.co/models?library=sentence-transformers
    Example: st:model-author/model-name

    --- TF-IDF ('tfidf:') ---
    tfidf:<your_custom_name> (e.g., tfidf:my_project_tfidf)
    Info: '<your_custom_name>' is chosen by you (e.g., 'tfidf:project_specific_terms').
           TF-IDF models are fitted on your data during 'add_document' (local fit)
           or 'add_vectorization' (global/targeted fit).
    ```

#### Choosing a Vectorizer (`vectorizer_name` parameter)

The `vectorizer_name` parameter in `add_document()` and `query()` tells `safe_store` which embedding model to use. It must match one of the naming conventions (`st:...` or `tfidf:...`).

### 4.4. Querying (`query`)

The `query()` method allows you to search for document chunks that are semantically similar to a given query text.

*   **How it works:**
    1.  The `query_text` is vectorized using the specified `vectorizer_name`.
    2.  `safe_store` retrieves all stored vectors associated with that `vectorizer_name`.
    3.  Cosine similarity is calculated between the query vector and all stored chunk vectors.
    4.  The top `top_k` chunks with the highest similarity scores are selected.
    5.  Details of these chunks (including their text, which is decrypted if necessary and the key is available) are retrieved and returned.

*   **`query(query_text: str, vectorizer_name: Optional[str] = None, top_k: int = 5)`**
    *   `query_text`: The text to search for.
    *   `vectorizer_name`: The vectorization method to use. Must match a method used during indexing. Defaults to `safe_store.DEFAULT_VECTORIZER` (`st:all-MiniLM-L6-v2`).
    *   `top_k`: The maximum number of similar chunks to return.

*   **Return Format:** A list of dictionaries. Each dictionary represents a relevant chunk and contains:
    *   `chunk_id` (int): ID of the chunk.
    *   `chunk_text` (str): The text content of the chunk.
        *   If encryption was enabled and the current `safe_store` instance has the correct `encryption_key`, this will be the decrypted plaintext.
        *   If encrypted but the key is missing: `"[Encrypted - Key Unavailable]"`.
        *   If encrypted but decryption fails (e.g., wrong key): `"[Encrypted - Decryption Failed]"`.
    *   `similarity` (float): The cosine similarity score (between -1.0 and 1.0, higher is more similar).
    *   `doc_id` (int): ID of the source document.
    *   `file_path` (str): Path to the source document file.
    *   `start_pos` (int): Start character offset of the chunk in the original document.
    *   `end_pos` (int): End character offset.
    *   `chunk_seq` (int): Sequence number of the chunk within the document.
    *   `metadata` (dict | None): Metadata associated with the source document.

```python
with safe_store.SafeStore("research_papers.db", encryption_key="mykey") as store:
    # Assume documents were added previously, possibly with encryption
    search_query = "advancements in neural network architecture"
    results = store.query(
        search_query,
        vectorizer_name="st:all-mpnet-base-v2", # Use a powerful model for querying
        top_k=3
    )
    for res in results:
        print(f"Found in '{Path(res['file_path']).name}' with score {res['similarity']:.3f}:")
        print(f"  Text: {res['chunk_text'][:200]}...") # Text will be decrypted
```

### 4.5. Encryption

`safe_store` provides optional encryption at rest for the `chunk_text` stored in the database. This enhances the security of sensitive document content.

*   **Enabling Encryption:**
    *   Provide a password string to the `encryption_key` parameter when initializing `safe_store`.
    *   Requires the `cryptography` library: `pip install safe_store[encryption]`.
    ```python
    store = safe_store.SafeStore(
        "my_secure_store.db",
        encryption_key="Th1sIsMyS3curePa$$wOrd!"
    )
    ```

*   **How it Works:**
    *   **Algorithm:** Uses Fernet symmetric encryption from the `cryptography` library, which combines AES-128 in CBC mode with HMAC for authentication.
    *   **Key Derivation:** A 256-bit encryption key suitable for Fernet is derived from your provided `encryption_key` (password) using PBKDF2HMAC-SHA256.
    *   **⚠️ Security Note on Salt:** For simplicity in this library version, `safe_store` uses a **fixed, hardcoded salt** during key derivation. This means the same password will always produce the same encryption key. While this simplifies key management for the user (no need to store a separate salt), it is less secure than using a unique, randomly generated salt per database or per encryption operation. Unique salts provide better protection against pre-computation attacks like rainbow tables. **Users should be aware of this trade-off.**
    *   **Key Management:** **You are solely responsible for managing your `encryption_key` (password).**
        *   **If you lose the password, your encrypted data will be unrecoverable.**
        *   Avoid hardcoding passwords directly in your scripts for production use. Use environment variables, configuration files with appropriate permissions, or dedicated secrets management tools.

*   **Impact on Operations:**
    *   **`add_document`:** If encryption is enabled, each `chunk_text` is encrypted before being written to the database. The `chunks` table has an `is_encrypted` flag that is set to true.
    *   **`query`:** When query results are retrieved, if a chunk was marked as encrypted and the current `safe_store` instance was initialized with the **correct** `encryption_key`, the `chunk_text` is automatically decrypted before being returned.
        *   If the key is not provided to the `safe_store` instance, `chunk_text` will be `"[Encrypted - Key Unavailable]"`.
        *   If the key is provided but is incorrect (or the data is corrupted), `chunk_text` will be `"[Encrypted - Decryption Failed]"`.
    *   **`add_vectorization` (for TF-IDF fitting):** If a TF-IDF model needs to be fitted and encryption is active, `safe_store` will attempt to decrypt the necessary chunk texts using the provided `encryption_key` before passing them to the TF-IDF fitter. If the key is missing or wrong, fitting on encrypted data will fail.

*   **What is Encrypted:**
    *   Only the `chunk_text` field in the `chunks` table is encrypted.
    *   Other data like document file paths, full document text (if stored, which it is), metadata, vector embeddings, vectorizer parameters, etc., are **NOT** encrypted by this feature.

*   **Example:** See `examples/encryption_usage.py` for a demonstration of using the encryption feature, including behavior with correct, missing, and incorrect keys.

### 4.6. Concurrency

`safe_store` is designed to handle concurrent access from multiple processes and threads.

*   **Process Safety (Inter-Process Concurrency):**
    *   `safe_store` uses the `filelock` library to manage a `.db.lock` file associated with your SQLite database.
    *   **Write Operations** (`add_document`, `add_vectorization`, `remove_vectorization`): These operations acquire an exclusive lock on the `.db.lock` file. If another process holds the lock, the current process will wait up to the `lock_timeout` duration. If the timeout is exceeded, a `ConcurrencyError` is raised.
    *   This ensures that database write operations are serialized across processes, preventing data corruption.

*   **Thread Safety (Intra-Process Concurrency):**
    *   `safe_store` uses an internal `threading.RLock` to protect its instance state, making individual `safe_store` method calls thread-safe within the same process.

*   **SQLite WAL Mode:**
    *   `safe_store` enables SQLite's Write-Ahead Logging (WAL) mode by default. WAL mode allows for significantly better concurrency, where readers do not block writers and writers do not block readers. This means `query()` operations (reads) can generally proceed even while another process is performing a write operation.

*   **`lock_timeout` Parameter:**
    *   When initializing `safe_store`, the `lock_timeout` parameter (default: 60 seconds) specifies how long a process should wait to acquire the write lock if it's already held.
    *   Setting `lock_timeout` to `0` or a negative value makes lock acquisition non-blocking; it will raise `ConcurrencyError` immediately if the lock cannot be acquired.

```python
# Process 1
store1 = safe_store.SafeStore("shared.db", lock_timeout=10)
with store1:
    store1.add_document("doc_a.txt") # Acquires lock

# Process 2 (running concurrently)
store2 = safe_store.SafeStore("shared.db", lock_timeout=10)
try:
    with store2:
        store2.add_document("doc_b.txt") # Will wait up to 10s if Process 1 holds lock
except safe_store.ConcurrencyError:
    print("Process 2: Could not acquire lock, store busy.")
```

### 4.7. Logging

`safe_store` uses the [`ascii_colors`](https://github.com/ParisNeo/ascii_colors) library for logging. This provides clear, leveled, and colorful console output by default.

*   **Default Behavior:**
    *   The default log level is `INFO`. Messages at `INFO`, `SUCCESS`, `WARNING`, `ERROR`, and `CRITICAL` levels will be printed to the console. `DEBUG` messages are hidden by default.
    *   Output includes timestamps, log levels (color-coded), and messages.

*   **Configuring Log Level in `safe_store.__init__`:**
    *   You can easily change the log level for a specific `safe_store` instance using the `log_level` parameter:
    ```python
    import safe_store
    from ascii_colors import LogLevel # LogLevel enum from ascii_colors

    # Show DEBUG messages and above
    store_debug = safe_store.SafeStore("debug_store.db", log_level=LogLevel.DEBUG)

    # Show only WARNING messages and above
    store_warn = safe_store.SafeStore("warn_store.db", log_level=LogLevel.WARNING)
    ```
    *   Available levels: `LogLevel.DEBUG`, `LogLevel.INFO`, `LogLevel.SUCCESS`, `LogLevel.WARNING`, `LogLevel.ERROR`, `LogLevel.CRITICAL`.

*   **Advanced Global Configuration (via `ASCIIColors` static methods):**
    Since `safe_store` uses `ascii_colors`, you can configure `ascii_colors` globally *in your application* (before initializing `safe_store` or any other library using `ascii_colors`) to customize logging behavior for all its users.
    *   **Setting Global Log Level:**
        ```python
        from ascii_colors import ASCIIColors, LogLevel
        ASCIIColors.set_log_level(LogLevel.DEBUG) # Affects all subsequent ascii_colors logs
        ```
    *   **Adding File Handlers:** Log to a file in addition to or instead of the console.
        ```python
        from ascii_colors import FileHandler
        file_handler = FileHandler("my_app.log", encoding='utf-8')
        ASCIIColors.add_handler(file_handler)
        ```
    *   **Customizing Formatters:** Change the log message format.
        ```python
        from ascii_colors import Formatter
        # Simple format for file
        file_formatter = Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)

        # JSON formatter for structured logging
        # from ascii_colors import JSONFormatter
        # json_handler = FileHandler("my_app.json.log")
        # json_handler.setFormatter(JSONFormatter())
        # ASCIIColors.add_handler(json_handler)
        ```
    *   **Removing Default Console Handler:** If you *only* want file logging.
        ```python
        default_console_handler = ASCIIColors.get_default_handler()
        if default_console_handler:
            ASCIIColors.remove_handler(default_console_handler)
        ```
    *   **Example:** See `examples/custom_logging.py` for a runnable demonstration of these global configurations.

### 4.8. Managing the Store

Besides indexing and querying, `safe_store` provides methods to inspect its contents:

*   **`list_documents()`**
    *   Returns a list of dictionaries, each containing information about a document stored in the database.
    *   Includes `doc_id`, `file_path`, `file_hash`, `added_timestamp`, and parsed `metadata`.
    ```python
    all_docs = store.list_documents()
    print(f"Total documents in store: {len(all_docs)}")
    for doc_info in all_docs:
        print(f"- {Path(doc_info['file_path']).name} (ID: {doc_info['doc_id']})")
        if doc_info['metadata']:
            print(f"  Metadata: {doc_info['metadata']}")
    ```

*   **`list_vectorization_methods()`**: (Covered in [Vectorization](#43-vectorization))
*   **`safe_store.list_possible_vectorizer_names()`**: (Covered in [Vectorization](#43-vectorization))

## 5. API Reference

This section details the public API of `safe_store`.

### `safe_store.safe_store`

The main class for interacting with the vector store.

*   **`__init__(db_path: Union[str, Path] = "safe_store.db", log_level: LogLevel = LogLevel.INFO, lock_timeout: int = DEFAULT_LOCK_TIMEOUT, encryption_key: Optional[str] = None)`**
    *   Initializes the store. See [Initialization](#initialization) for parameter details.

*   **`add_document(file_path: Union[str, Path], vectorizer_name: Optional[str] = None, chunk_size: int = 1000, chunk_overlap: int = 150, metadata: Optional[Dict[str, Any]] = None, force_reindex: bool = False, vectorizer_params: Optional[Dict[str, Any]] = None)`**
    *   Adds or updates a document. See [Document Indexing](#42-document-indexing-add_document) for details.

*   **`query(query_text: str, vectorizer_name: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]`**
    *   Queries for similar document chunks. See [Querying](#44-querying-query) for details.

*   **`add_vectorization(vectorizer_name: str, target_doc_path: Optional[Union[str, Path]] = None, vectorizer_params: Optional[Dict[str, Any]] = None, batch_size: int = 64) -> None`**
    *   Adds a new vectorization method to existing documents. See [Managing Vectorizations](#managing-vectorizations) for details.

*   **`remove_vectorization(vectorizer_name: str) -> None`**
    *   Removes a vectorization method and its associated vectors. See [Managing Vectorizations](#managing-vectorizations) for details.

*   **`list_documents() -> List[Dict[str, Any]]`**
    *   Returns a list of all documents in the store. See [Managing the Store](#48-managing-the-store) for details.

*   **`list_vectorization_methods() -> List[Dict[str, Any]]`**
    *   Returns a list of all registered vectorization methods. See [Managing Vectorizations](#managing-vectorizations) for details.

*   **`@staticmethod list_possible_vectorizer_names() -> List[str]`**
    *   Returns a list of example and common vectorizer names and patterns. See [Managing Vectorizations](#managing-vectorizations) for details.

*   **`close() -> None`**
    *   Manually closes the database connection. See [Closing the Store](#closing-the-store).

*   **`__enter__(self) -> SafeStore`** and **`__exit__(self, exc_type, exc_val, exc_tb)`**
    *   Support for context manager protocol. See [Context Manager Usage](#context-manager-usage).

### `safe_store.LogLevel`

An enumeration (from `ascii_colors.LogLevel`) used for setting log levels.
Values: `DEBUG`, `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL`.

```python
from safe_store import LogLevel
level = LogLevel.DEBUG
```

### Exceptions

`safe_store` uses custom exceptions to indicate various error conditions. All custom exceptions inherit from `safe_store.SafeStoreError`.

*   `SafeStoreError(Exception)`: Base class for all `safe_store` specific errors.
*   `DatabaseError(SafeStoreError)`: Errors related to database operations (connection, schema, query, transaction).
*   `FileHandlingError(SafeStoreError)`: Errors related to file system operations (reading, writing, hashing, not found).
*   `ParsingError(FileHandlingError)`: Errors occurring during document parsing.
*   `ConfigurationError(SafeStoreError)`: Errors related to invalid configuration, setup, or missing optional dependencies.
*   `IndexingError(SafeStoreError)`: Errors specifically within the document indexing pipeline orchestration (not sub-steps like parsing or vectorization).
*   `VectorizationError(SafeStoreError)`: Errors related to vectorization processes (model loading, encoding, fitting).
*   `QueryError(SafeStoreError)`: Errors occurring during query execution.
*   `ConcurrencyError(SafeStoreError)`: Errors related to file locking or concurrent access issues (e.g., timeouts).
*   `EncryptionError(SafeStoreError)`: Errors related to data encryption or decryption.

You can catch these specific exceptions to handle errors more gracefully in your application.

```python
import safe_store

try:
    with safe_store.SafeStore("mystore.db", encryption_key="bad-key-format!") as store: # Example bad key
        # ...
        pass
except safe_store.ConfigurationError as e:
    print(f"Configuration problem: {e}")
except safe_store.EncryptionError as e:
    print(f"Encryption setup or operation failed: {e}")
except safe_store.DatabaseError as e:
    print(f"Database issue: {e}")
except safe_store.SafeStoreError as e: # Catch-all for library errors
    print(f"A safe_store error occurred: {e}")
except Exception as e:
    print(f"An unexpected general error: {e}")
```

## 6. Examples

The `safe_store` repository includes an `examples/` directory with runnable Python scripts demonstrating various features:

*   **`examples/basic_usage.py`**: Shows the core workflow of initializing the store, adding different types of documents with Sentence Transformer and TF-IDF vectorizations, querying using both methods, handling file updates, listing documents and vectorizers, and removing a vectorization.
*   **`examples/custom_logging.py`**: Demonstrates how to globally configure `ascii_colors` to customize `safe_store`'s logging output, such as changing the log level, logging to a file, and setting custom log formats.
*   **`examples/encryption_usage.py`**: Illustrates how to use `safe_store`'s encryption feature. It covers initializing an encrypted store, adding documents (which get encrypted), querying (with automatic decryption), and how the store behaves when accessed without the correct encryption key or with a wrong key.

It's highly recommended to run these examples to see `safe_store` in action and adapt them for your own use cases.

## 7. Error Handling

As detailed in the [Exceptions](#exceptions) section, `safe_store` raises specific custom exceptions for different error conditions. Your application should use `try-except` blocks to catch and handle these errors appropriately.

Common scenarios and exceptions to anticipate:

*   **Missing Optional Dependencies:** `ConfigurationError` will be raised if you try to use a feature (e.g., parse a PDF, use Sentence Transformers) without the necessary libraries installed. The error message usually includes instructions on how to install the missing extra.
*   **File Issues:** `FileHandlingError` (or `ParsingError`) for problems like file not found, permission errors, or unparseable file formats.
*   **Database Problems:** `DatabaseError` for issues with the SQLite database itself (e.g., disk full, corrupted file).
*   **Concurrency Timeouts:** `ConcurrencyError` if a write lock cannot be acquired within the `lock_timeout`.
*   **Encryption Issues:** `EncryptionError` for problems during key derivation, encryption, or decryption (e.g., wrong key, tampered data). `ConfigurationError` can also be raised if encryption is requested but `cryptography` is not installed.

Always ensure your `safe_store` instance is properly closed, ideally by using it as a context manager, to prevent resource leaks or locked database files.

## 8. Future Work

Based on the project's `plan.md` and `README.md`, potential future enhancements include:

*   **Re-indexing Method:** A dedicated `reindex()` method to re-process documents with new chunking or other parameters without needing the original file.
*   **More Vectorizers:** Integrations for OpenAI, Cohere, Ollama embeddings.
*   **Metadata Filtering:** Allow filtering query results based on document metadata.
*   **Performance Optimizations:** Exploration of Approximate Nearest Neighbor (ANN) indexing (e.g., Faiss, HNSWlib) for very large datasets.
*   **Async API:** Consideration for an asynchronous interface using `aiosqlite`.
*   **Enhanced Encryption:** Options for unique salts per database or per chunk for improved security.

## 9. Contributing

Contributions to `safe_store` are welcome! Please feel free to open an issue to discuss bugs or feature requests, or submit a pull request on the [GitHub repository](https://github.com/ParisNeo/safe_store).

Before contributing, please review the project's coding style and testing practices. (A formal `CONTRIBUTING.md` may be added in the future).

## 10. Changelog

All notable changes to this project are documented in the `CHANGELOG.md` file in the repository. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 11. License

`safe_store` is licensed under the Apache License 2.0. See the `LICENSE` file in the repository for the full license text.