    # LoLLMs Client Library Documentation

    *Generated: 2025-05-06 (Based on files up to 2025-05-06 16:30:13)*

    Welcome to the complete documentation for the `lollms_client` Python library. This library provides a powerful and flexible client for interacting with various Large Language Model (LLM) backends, including the main LoLLMs service, Ollama, OpenAI-compatible APIs, and local Transformers models.

    ## Table of Contents

    1.  [Overview](#1-overview)
        *   [What is lollms\_client?](#what-is-lollms_client)
        *   [Key Features](#key-features)
    2.  [Installation](#2-installation)
    3.  [Getting Started](#3-getting-started)
        *   [Basic LollmsClient Instantiation](#basic-lollmsclient-instantiation)
        *   [Text Generation](#text-generation)
        *   [Code Generation](#code-generation)
        *   [Listing Models and Personalities](#listing-models-and-personalities)
    4.  [Core Components](#4-core-components)
        *   [LollmsClient (`lollms_core.py`)](#lollmsclient-lollms_corepy)
            *   [Initialization Parameters](#initialization-parameters)
            *   [Key Methods](#key-methods)
        *   [TasksLibrary (`lollms_tasks.py`)](#taskslibrary-lollms_taskspy)
            *   [Initialization](#initialization)
            *   [Key Methods](#key-methods-1)
        *   [LollmsPersonality (`lollms_personality.py`)](#lollmspersonality-lollms_personalitypy)
        *   [LollmsDiscussion & LollmsMessage (`lollms_discussion.py`)](#lollmsdiscussion--lollmsmessage-lollms_discussionpy)
        *   [FunctionCalling\_Library (`lollms_functions.py`)](#functioncalling_library-lollms_functionspy)
        *   [LollmsTTS (`lollms_tts.py`)](#lollmstts-lollms_ttspy)
        *   [LollmsSTT (`lollms_stt.py`)](#lollmsstt-lollms_sttpy)
    5.  [LLM Bindings (`lollms_client/llm_bindings/`)](#5-llm-bindings-lollms_clientllm_bindings)
        *   [Binding Architecture (`lollms_llm_binding.py`)](#binding-architecture-lollms_llm_bindingpy)
        *   [LollmsLLMBinding (`lollms_client/llm_bindings/lollms/`)](#lollmsllmbinding-lollms_clientllm_bindingslollms)
        *   [OllamaBinding (`lollms_client/llm_bindings/ollama/`)](#ollamabinding-lollms_clientllm_bindingsollama)
        *   [OpenAIBinding (`lollms_client/llm_bindings/openai/`)](#openaibinding-lollms_clientllm_bindingsopenai)
        *   [TransformersBinding (`lollms_client/llm_bindings/transformers/`)](#transformersbinding-lollms_clientllm_bindingstransformers)
    6.  [Configuration (`lollms_config.py`)](#6-configuration-lollms_configpy)
    7.  [Types (`lollms_types.py`)](#7-types-lollms_typespy)
    8.  [Utilities (`lollms_utilities.py`)](#8-utilities-lollms_utilitiespy)
    9.  [Examples](#9-examples)
        *   [Article Summary (`examples/article_summary/`)](#article-summary-examplesarticle_summary)
        *   [Deep Analysis (`examples/deep_analyze/`)](#deep-analysis-examplesdeep_analyze)
        *   [Function Calling (`examples/function_call/`)](#function-calling-examplesfunction_call)
        *   [Personality Tests (`examples/personality_test/`)](#personality-tests-examplespersonality_test)
        *   [Local Model Testing (`examples/test_local_models/`)](#local-model-testing-examplestest_local_models)
        *   [Text to Audio (`examples/text_2_audio.py`)](#text-to-audio-examplestext_2_audiopy)
        *   [Text and Image to Audio (`examples/text_and_image_2_audio.py`)](#text-and-image-to-audio-examplestext_and_image_2_audiopy)
        *   [Text Generation (`examples/text_gen.py`)](#text-generation-examplestext_genpy)
    10. [Code Analysis Tools](#10-code-analysis-tools)
        *   [Python Analyzer (`lollms_python_analyzer.py`)](#python-analyzer-lollms_python_analyzerpy)
        *   [JavaScript Analyzer (`lollms_js_analyzer.py`)](#javascript-analyzer-lollms_js_analyzerpy)
    11. [File Structure](#11-file-structure)
    12. [Changelog](#12-changelog)
    13. [Dependencies](#13-dependencies)
    14. [License](#14-license)
    15. [External Documentation: `ascii_colors`](#15-external-documentation-ascii_colors)

    ---

    ## 1. Overview

    ### What is lollms_client?

    `lollms_client` is a Python library designed to simplify interactions with the Lord Of Large Language Models (LoLLMs) ecosystem and other compatible LLM backends. It provides a unified interface for tasks such as text generation, code generation, image-based prompting, text-to-speech, speech-to-text, and managing personalities and models.

    This client allows developers to easily integrate powerful AI capabilities into their Python applications, whether they are connecting to a local LoLLMs server, a remote instance, or other services like Ollama and OpenAI.

    ### Key Features

    *   **Multi-Backend Support:** Connect to LoLLMs, Ollama, OpenAI-compatible APIs, and local Hugging Face Transformers models.
    *   **Text Generation:** Generate text with options for streaming, temperature, top-k, top-p, and repetition penalties.
    *   **Multimodal Input:** Support for prompts that include both text and images.
    *   **Code Generation:** Specialized methods for generating code snippets, including JSON/YAML structured data.
    *   **Task Automation:** A `TasksLibrary` for common LLM tasks like summarization, Q&A, and function calling.
    *   **Personality Management:** Interact with LoLLMs personalities, including loading and generating with them.
    *   **Discussion Handling:** Manage and format conversation histories.
    *   **Function Calling:** Define and execute functions based on LLM-generated instructions.
    *   **Text-to-Speech (TTS) & Speech-to-Text (STT):** Integrate with LoLLMs services for audio processing.
    *   **Extensible Bindings:** Easily add support for new LLM backends.
    *   **Configuration Management:** Flexible system for handling configurations.

    ---

    ## 2. Installation

    To install the library from PyPI using `pip`, run:

    ```bash
    pip install lollms-client
    ```

    Ensure you have Python 3.8 or higher. Dependencies are listed in `requirements.txt` and will be installed automatically.

    ---

    ## 3. Getting Started

    The `LollmsClient` class is the primary entry point for using the library.

    ### Basic LollmsClient Instantiation

    ```python
    from lollms_client import LollmsClient

    # Default: Connects to a local LoLLMs service (http://localhost:9600)
    # using the "lollms" binding.
    lc = LollmsClient()

    # Specify a custom host for the LoLLMs service
    # lc = LollmsClient(host_address="http://your.lollms.server:9600")

    # Use a specific model with a local Ollama server
    # Assumes Ollama is running on http://localhost:11434
    # lc = LollmsClient(binding_name="ollama", model_name="phi3:latest")

    # Use Ollama with a custom host and context size
    # lc = LollmsClient(
    #     binding_name="ollama",
    #     host_address="http://your.ollama.server:11434",
    #     model_name="llama2:latest",
    #     ctx_size=8192  # Example context size
    # )

    # Use a specific model with an OpenAI-compatible server
    # Set your API key as an environment variable OPENAI_API_KEY
    # or pass it via service_key
    # lc = LollmsClient(
    #     binding_name="openai",
    #     model_name="gpt-3.5-turbo",
    #     # service_key="YOUR_OPENAI_API_KEY" # Optional
    # )

    # Use a local Hugging Face Transformers model
    # Ensure you have transformers, torch, and accelerate installed
    # lc = LollmsClient(binding_name="transformers", model_name="microsoft/Phi-3-mini-4k-instruct")
    ```

    ### Text Generation

    Use `generate_text()` for most text generation tasks.

    ```python
    # Simple text generation
    response = lc.generate_text(prompt="Tell me a short story about a brave robot.", stream=False, temperature=0.7, n_predict=200)
    print(response)

    # Text generation with image input (requires a model that supports vision)
    # Assuming lc is configured with a vision-capable binding/model (e.g., LLaVA with Ollama, or GPT-4V with OpenAI)
    # response = lc.generate_text(
    #     prompt="Describe this image:",
    #     images=["path/to/your/image.jpg"],
    #     stream=False,
    #     n_predict=150
    # )
    # print(response)

    # Streaming response
    def my_streaming_callback(chunk, msg_type):
        print(chunk, end="", flush=True)
        return True # Return False to stop streaming

    print("\nStreaming response:")
    lc.generate_text(
        prompt="What is the capital of France?",
        streaming_callback=my_streaming_callback,
        stream=True
    )
    print()
    ```

    ### Code Generation

    The `generate_code()` method is specialized for generating code or structured data.

    ```python
    import json

    # Generate a Python function
    python_code = lc.generate_code(
        prompt="Create a Python function to calculate the factorial of a number.",
        language='python'
    )
    print("Generated Python Code:\n", python_code)

    # Generate JSON data based on a template
    json_template = """
    {
    "name": "the first name of the person",
    "family_name": "the family name of the person",
    "age": "the age of the person",
    "appointment_date": "the date of the appointment in DD/MM/YYYY format",
    "reason": "the reason for the appointment (N/A if not specified)"
    }
    """
    user_request = "Mr. Alex Brown presents himself. He is 30 years old and seeks an appointment for the 25th of December 2025 for a check-up."

    json_response = lc.generate_code(
        prompt=user_request,
        language='json',
        template=json_template
    )
    print("\nGenerated JSON Data:\n", json_response)
    try:
        data = json.loads(json_response)
        print(f"\nParsed Data: Name: {data.get('name')} {data.get('family_name')}, Reason: {data.get('reason')}")
    except json.JSONDecodeError:
        print("Failed to parse JSON response.")
    ```

    ### Listing Models and Personalities

    ```python
    # List available models for the current binding
    models = lc.listModels()
    if isinstance(models, list) and models:
        print(f"\nAvailable models for binding '{lc.binding.get_model_info()['name']}':")
        for model_info in models[:5]: # Print first 5
            if isinstance(model_info, dict):
                print(f"  - {model_info.get('model_name', model_info.get('id', 'Unknown Model'))}")
            else: # some bindings might return a list of strings
                print(f"  - {model_info}")

    elif isinstance(models, dict) and 'error' in models:
        print(f"Error listing models: {models['error']}")
    else:
        print("No models listed or unexpected format.")


    # List mounted personalities (specific to "lollms" binding)
    if lc.binding.get_model_info()['name'] == 'lollms':
        personalities = lc.binding.lollms_listMountedPersonalities()
        if isinstance(personalities, list) and personalities:
            print("\nMounted LoLLMs Personalities:")
            for p in personalities[:5]: # Print first 5
                print(f"  - {p.get('name', 'Unknown Personality')} (Category: {p.get('category', 'N/A')})")
        elif isinstance(personalities, dict) and 'error' in personalities:
            print(f"Error listing personalities: {personalities['error']}")
        else:
            print("No personalities listed or already using a non-lollms binding.")
    ```

    ---

    ## 4. Core Components

    ### LollmsClient (`lollms_core.py`)

    The `LollmsClient` class is the main interface for interacting with LLM bindings.

    #### Initialization Parameters

    ```python
    class LollmsClient:
        def __init__(self,
                    binding_name: str = "lollms",
                    host_address: Optional[str] = None,
                    model_name: str = "",
                    service_key: Optional[str] = None,
                    verify_ssl_certificate: bool = True,
                    personality: Optional[int] = None, # Used by 'lollms' binding
                    llm_bindings_dir: Path = Path(__file__).parent / "llm_bindings",
                    binding_config: Optional[Dict[str, any]] = None,
                    ctx_size: Optional[int] = 8192,
                    n_predict: Optional[int] = 4096,
                    stream: bool = False,
                    temperature: float = 0.1,
                    top_k: int = 50,
                    top_p: float = 0.95,
                    repeat_penalty: float = 0.8,
                    repeat_last_n: int = 40,
                    seed: Optional[int] = None,
                    n_threads: int = 8,
                    streaming_callback: Optional[Callable[[str, MSG_TYPE], None]] = None,
                    user_name: str ="user",
                    ai_name: str = "assistant"
                    ) -> None
    ```

    *   `binding_name`: Name of the binding to use (e.g., "lollms", "ollama", "openai", "transformers").
    *   `host_address`: Host address for the LLM service. Overrides binding default if provided.
    *   `model_name`: Name of the model to use.
    *   `service_key`: Authentication key for the service (e.g., OpenAI API key).
    *   `verify_ssl_certificate`: Whether to verify SSL certificates.
    *   `personality`: Personality ID (used by the "lollms" binding).
    *   `llm_bindings_dir`: Directory containing binding implementations.
    *   `binding_config`: Additional configuration for the specific binding.
    *   `ctx_size`: Default context size for the model.
    *   `n_predict`: Default maximum number of tokens to predict.
    *   `stream`: Default streaming mode (True/False).
    *   `temperature`, `top_k`, `top_p`, `repeat_penalty`, `repeat_last_n`, `seed`, `n_threads`: Default generation parameters.
    *   `streaming_callback`: Default callback function for streaming responses.
    *   `user_name`, `ai_name`: Default names for user and AI in formatted prompts.

    #### Key Methods

    *   `tokenize(text: str) -> list`: Tokenizes text using the active binding.
    *   `detokenize(tokens: list) -> str`: Detokenizes tokens using the active binding.
    *   `get_model_details() -> dict`: Gets information about the current model from the active binding.
    *   `switch_model(model_name: str) -> bool`: Loads a new model in the active binding.
    *   `get_available_bindings() -> List[str]`: Returns a list of available binding names.
    *   `generate_text(prompt: str, images: Optional[List[str]] = None, ... ) -> str`:
        Generates text. Accepts all generation parameters, overriding defaults if provided.
        If `images` are provided, it attempts multimodal generation.
    *   `embed(text: str)`: Generates embeddings for the input text using the active binding.
    *   `listModels() -> list`: Lists models available to the current binding.
    *   `generate_code(prompt: str, images: Optional[List[str]] = [], template: Optional[str] = None, language: str = "json", ... ) -> str`:
        Generates a single code block. Useful for structured output like JSON/YAML or actual code.
        `template` can guide the LLM for the structure. `language` specifies the language tag.
    *   `generate_codes(prompt: str, images: Optional[List[str]] = [], template: Optional[str] = None, language: str = "json", ... ) -> List[dict]`:
        Generates multiple code blocks.
    *   `extract_code_blocks(text: str, format: str = "markdown") -> List[dict]`: Extracts code blocks from text. `format` can be "markdown" or "html".
    *   `extract_thinking_blocks(text: str) -> List[str]`: Extracts content from `<thinking>` or `<think>` tags.
    *   `remove_thinking_blocks(text: str) -> str`: Removes `<thinking>` or `<think>` blocks and their content.
    *   `yes_no(question: str, ... ) -> bool | dict`: Answers a yes/no question. Can return an explanation.
    *   `multichoice_question(question: str, possible_answers: list, ... ) -> int | dict`: Interprets a multi-choice question.
    *   `multichoice_ranking(question: str, possible_answers: list, ... ) -> dict`: Ranks answers for a question.
    *   `sequential_summarize(text: str, chunk_processing_prompt: str, ... ) -> str`:
        Processes text in chunks to generate a summary, updating a memory at each step.
    *   `deep_analyze(query: str, text: Optional[str] = None, files: Optional[list] = None, ... ) -> str`:
        Searches for information related to a query in a long text or list of files, processing in chunks and updating a shared memory.

    For detailed parameters of each method, refer to `ai_documentation/lollms_core_classes.md` and the source code.

    ### TasksLibrary (`lollms_tasks.py`)

    The `TasksLibrary` provides higher-level task abstractions built on top of `LollmsClient`.

    #### Initialization

    ```python
    from lollms_client import LollmsClient, TasksLibrary

    lc = LollmsClient()
    tl = TasksLibrary(lc) # Optionally pass a default callback
    # tl.setCallback(my_custom_callback)
    ```

    #### Key Methods (from `ai_documentation/lollms_tasks_classes.md` and source)

    *   `generate(prompt, n_predict, ...)`: Similar to `LollmsClient.generate_text` but uses `TasksLibrary`'s internal callback and processing logic.
    *   `fast_gen(prompt: str, n_predict: int, ...)`: A utility for reshaping prompts to fit context limits before generation.
    *   `generate_with_images(prompt, images, n_predict, ...)`: Generation with image support.
    *   `fast_gen_with_images(prompt: str, images: list, ...)`: `fast_gen` equivalent for image-based prompts.
    *   `step_start(step_text, callback=None)`: Signals the start of a task step via callback.
    *   `step_end(step_text, status=True, callback=None)`: Signals the end of a task step.
    *   `step(step_text, callback=None)`: Signals an intermediate step.
    *   `translate_text_chunk(text_chunk, output_language="french", ...)`: Translates a text chunk.
    *   `extract_code_blocks(text: str) -> List[dict]`: Extracts code blocks (delegates to `LollmsClient`).
    *   `yes_no(question: str, context: str = '', ...)`: Answers yes/no questions.
    *   `multichoice_question(question: str, possible_answers: list, ...)`: Handles multiple-choice questions.
    *   `summerize_text(text, summary_instruction="summerize", ...)`: Summarizes text using various modes.
    *   `smart_data_extraction(text, data_extraction_instruction="summerize", ...)`: Multi-step summarization and reformulation.
    *   `summerize_chunks(chunks, summary_instruction="summerize", ...)`: Summarizes pre-defined chunks of text.
    *   **Function Calling Methods:**
        *   `_upgrade_prompt_with_function_info(prompt: str, functions: List[Dict]) -> str`: Adds function definitions to a prompt.
        *   `extract_function_calls_as_json(text: str) -> List[Dict]`: Parses function calls from LLM output.
        *   `execute_function_calls(function_calls: List[Dict], function_definitions: List[Dict]) -> List[Any]`: Executes parsed function calls.
        *   `generate_with_function_calls(prompt: str, functions: List[Dict], ... ) -> Tuple[str, List[Dict]]`: Generates text and extracts function calls.
        *   `generate_with_function_calls_and_images(prompt: str, images: list, functions: List[Dict], ... ) -> Tuple[str, List[Dict]]`: Same as above, but with image support.

    ### LollmsPersonality (`lollms_personality.py`)

    Represents a LoLLMs personality, encapsulating its configuration, conditioning, and interaction logic.

    ```python
    from lollms_client import LollmsClient, LollmsPersonality, LollmsDiscussion, MSG_TYPE

    lc = LollmsClient() # Assuming LoLLMs binding for personality interaction

    def my_callback(chunk, msg_type: MSG_TYPE, params=None, metadata=None):
        print(f"Type: {msg_type.name}, Chunk: {chunk}")
        if params: print(f"Params: {params}")
        return True

    # Example of creating an inline personality (not from a package)
    inline_persona = LollmsPersonality(
        lollmsClient=lc,
        personality_work_dir="./temp_work_dir",
        personality_config_dir="./temp_config_dir",
        callback=my_callback,
        name="MyHelper",
        user_name="User",
        personality_conditioning="!@>system: You are a helpful AI assistant.",
        welcome_message="Hello! I am MyHelper. How can I assist you?"
    )

    # To load a personality from a package:
    # mounted_personas = lc.listMountedPersonalities() # If using lollms binding
    # if mounted_personas and isinstance(mounted_personas, list) and len(mounted_personas)>0:
    #     first_persona_path = mounted_personas[0].get("path") # This is a placeholder; actual path retrieval might differ
    #     if first_persona_path:
    #         loaded_persona = LollmsPersonality(
    #             lollmsClient=lc,
    #             personality_package_path=first_persona_path,
    #             callback=my_callback
    #             # work/config dirs would typically be derived or fixed
    #         )
    #         print(f"Loaded persona: {loaded_persona.name}")

    discussion = LollmsDiscussion(lc)
    # inline_persona.generate(discussion, "What is the weather like today?", stream=True)
    ```

    Key attributes and methods:
    *   `__init__`: Takes `LollmsClient`, paths for work/config directories, a callback, and optionally all personality attributes (author, name, conditioning, etc.). Can also load from `personality_package_path`.
    *   `load_personality(package_path=None)`: Loads personality configuration from a YAML file within its package.
    *   `generate(discussion: LollmsDiscussion, prompt: str, ...)`: Generates a response using the personality's conditioning and the discussion context.
    *   `fast_gen(prompt: str, ...)`: Quick generation, similar to `TasksLibrary.fast_gen`.

    ### LollmsDiscussion & LollmsMessage (`lollms_discussion.py`)

    `LollmsMessage` is a dataclass for individual messages (sender, content, id).
    `LollmsDiscussion` manages a list of `LollmsMessage` objects.

    ```python
    from lollms_client import LollmsClient, LollmsDiscussion, LollmsMessage

    lc = LollmsClient()
    discussion = LollmsDiscussion(lc)

    discussion.add_message(sender="user", content="Hello AI!")
    discussion.add_message(sender="assistant", content="Hello User!")

    # Format for LLM input, respecting token limits
    formatted_history = discussion.format_discussion(max_allowed_tokens=512)
    print(formatted_history)

    # Save to YAML
    # discussion.save_to_disk("my_discussion.yaml")
    ```

    *   `LollmsDiscussion.add_message(sender, content)`
    *   `LollmsDiscussion.save_to_disk(file_path)`
    *   `LollmsDiscussion.format_discussion(max_allowed_tokens, splitter_text="!@>")`

    ### FunctionCalling_Library (`lollms_functions.py`)

    Manages defining and executing functions based on LLM outputs.

    ```python
    from lollms_client import LollmsClient, TasksLibrary, FunctionCalling_Library

    lc = LollmsClient()
    tl = TasksLibrary(lc)
    fcl = FunctionCalling_Library(tl) # Depends on TasksLibrary

    # Define a function
    def get_current_weather(location: str, unit: str = "celsius"):
        # Mock implementation
        if "paris" in location.lower():
            return f"The weather in Paris is sunny, 25 {unit}."
        return f"Weather data for {location} not found."

    fcl.register_function(
        function_name="get_current_weather",
        function_callable=get_current_weather,
        function_description="Get the current weather in a given location.",
        function_parameters=[
            {"name": "location", "type": "string", "description": "The city and state, e.g. San Francisco, CA"},
            {"name": "unit", "type": "string", "enum": ["celsius", "fahrenheit"], "description": "The unit of temperature"}
        ]
    )

    user_prompt = "User: What's the weather like in Paris?\nAssistant:"
    ai_response, function_calls = fcl.generate_with_functions(user_prompt)

    print("AI Response:", ai_response)
    if function_calls:
        print("Function Calls:", function_calls)
        results = fcl.execute_function_calls(function_calls)
        print("Execution Results:", results)

        # Potentially feed results back to the LLM
        # followup_prompt = f"{user_prompt}{ai_response}\nFunction Execution Result: {results[0]}\nAssistant:"
        # final_response, _ = fcl.generate_with_functions(followup_prompt)
        # print("Final AI Response:", final_response)
    ```

    *   `register_function(function_name, function_callable, function_description, function_parameters)`
    *   `unregister_function(function_name)`
    *   `execute_function_calls(function_calls: List[Dict]) -> List[Any]`: Executes calls using previously registered functions.
    *   `generate_with_functions(prompt, ...)`: Generates text and attempts to parse function calls.
    *   `generate_with_functions_and_images(prompt, images, ...)`: Same as above with image support.

    ### LollmsTTS (`lollms_tts.py`)

    Client for LoLLMs Text-to-Speech service.

    ```python
    from lollms_client import LollmsClient, LollmsTTS

    lc = LollmsClient() # Assuming connected to a LoLLMs instance with TTS service
    tts = LollmsTTS(lc)

    try:
        voices = tts.get_voices()
        if voices:
            print("Available TTS voices:", voices)
            selected_voice = voices[0] # Example
            # result = tts.text2Audio("Hello world, this is a test.", voice=selected_voice, fn="output.wav")
            # print("TTS Result:", result) # Should indicate success or provide file path
        else:
            print("No TTS voices found or TTS service not available.")
    except Exception as e:
        print(f"Error with TTS: {e}")
    ```

    *   `text2Audio(text, voice=None, fn=None)`: Converts text to audio, saves to `fn`.
    *   `get_voices()`: Lists available TTS voices from the server.

    ### LollmsSTT (`lollms_stt.py`)

    Client for LoLLMs Speech-to-Text service. (Note: The provided `lollms_stt.py` seems to have copy-pasted content from TTS, I'll assume its intended functionality).

    ```python
    # Presumed functionality for LollmsSTT
    # from lollms_client import LollmsClient, LollmsSTT

    # lc = LollmsClient() # Assuming connected to LoLLMs with STT service
    # stt = LollmsSTT(lc)

    # try:
    #     models = stt.get_models() # Or similar method to list STT models
    #     if models:
    #         print("Available STT models:", models)
    #         # result = stt.audio2text(wave_file_path="path/to/audio.wav", model=models[0])
    #         # print("STT Result:", result) # Should contain transcribed text
    #     else:
    #         print("No STT models found or STT service not available.")
    # except Exception as e:
    #     print(f"Error with STT: {e}")
    ```
    *   `audio2text(wave_file_path: str, model=None)`: Converts audio file to text.
    *   `get_models()` (or similar, e.g., `get_stt_models`): Lists available STT models. *(Method name based on TTS pattern, actual may vary)*.

    ---

    ## 5. LLM Bindings (`lollms_client/llm_bindings/`)

    Bindings are Python modules that allow `LollmsClient` to communicate with different LLM backends.

    ### Binding Architecture (`lollms_llm_binding.py`)

    *   **`LollmsLLMBinding(ABC)`**: An abstract base class defining the interface all specific bindings must implement. Key abstract methods include `generate_text`, `tokenize`, `detokenize`, `embed`, `get_model_info`, `listModels`, `load_model`.
    *   **`LollmsLLMBindingManager`**: Manages the discovery and instantiation of available bindings from the `llm_bindings` directory. `LollmsClient` uses this manager to create the appropriate binding instance.

    ### LollmsLLMBinding (`lollms_client/llm_bindings/lollms/`)

    This is the binding for the native LoLLMs API.
    *   **Default Host:** `http://localhost:9600`
    *   **Endpoints Used:**
        *   `/lollms_generate` (text-only)
        *   `/lollms_generate_with_images` (text and images)
        *   `/lollms_tokenize`
        *   `/lollms_detokenize`
        *   `/lollms_embed`
        *   `/list_models`
        *   `/list_mounted_personalities` (specific to this binding)
    *   **Initialization:** Can take a `personality` ID.
    *   **Functionality:** Supports text generation, image input, tokenization, detokenization, embeddings, listing models, and listing mounted personalities.

    ### OllamaBinding (`lollms_client/llm_bindings/ollama/`)

    Connects to an Ollama server.
    *   **Default Host:** `http://localhost:11434`
    *   **Endpoints Used:**
        *   `/api/generate` (text-only)
        *   `/api/chat` (for multimodal with images, or general chat)
        *   `/api/embed`
        *   `/api/tags` (for `listModels`)
    *   **Functionality:**
        *   `generate_text`: Uses `/api/chat` if images are provided (formatting messages with image data), otherwise uses `/api/generate`.
        *   `tokenize`/`detokenize`: Simple character-level tokenization as Ollama handles tokenization internally.
        *   `embed`: Uses Ollama's `/api/embed`.
        *   `listModels`: Fetches model tags from `/api/tags`.

    ### OpenAIBinding (`lollms_client/llm_bindings/openai/`)

    Connects to an OpenAI API or any OpenAI-compatible endpoint.
    *   **Default Host:** `https://api.openai.com/v1` (can be overridden for other compatible services)
    *   **Dependencies:** `openai`, `tiktoken` Python libraries.
    *   **Authentication:** Uses `service_key` (API key), which can also be set via the `OPENAI_API_KEY` environment variable.
    *   **Endpoints Used (via `openai` library):**
        *   `client.chat.completions.create` (for chat models, or if `completion_format` is `ELF_COMPLETION_FORMAT.Chat`, and for image input)
        *   `client.completions.create` (for older instruction-following models if `completion_format` is `ELF_COMPLETION_FORMAT.Instruct`)
        *   `client.models.list` (for `listModels`)
    *   **Functionality:**
        *   `generate_text`: Handles text and image input (for vision-capable models). Uses chat completions for image input.
        *   `tokenize`/`detokenize`: Uses `tiktoken` based on the `model_name`.
        *   `listModels`: Fetches models from the `/v1/models` endpoint.
        *   `embed`: (Placeholder in provided code, would typically use `client.embeddings.create`)

    ### TransformersBinding (`lollms_client/llm_bindings/transformers/`)

    Allows running Hugging Face Transformers models locally.
    *   **Dependencies:** `torch`, `transformers`. Automatically attempts to install/reinstall with CUDA support if not found or misconfigured.
    *   **Initialization:**
        *   Loads model and tokenizer using `AutoModelForCausalLM.from_pretrained` and `AutoTokenizer.from_pretrained`.
        *   Configures 4-bit quantization (`BitsAndBytesConfig`) for efficient local execution.
        *   Infers a `prompt_template` based on model name (e.g., Llama-2, GPT-style) or uses a provided one.
    *   **Functionality:**
        *   `generate_text`:
            *   Applies the prompt template (system prompt + user prompt).
            *   Uses `model.generate()` for text generation.
            *   Supports streaming via a callback.
            *   Image input is acknowledged but not deeply processed in the current implementation ("Image content not processed").
        *   `tokenize`/`detokenize`: Simple character-level, as the main tokenization happens internally via the Hugging Face tokenizer.
        *   `embed`, `listModels`: Placeholders in the provided code.

    ---

    ## 6. Configuration (`lollms_config.py`)

    This module provides classes for managing configurations, often used by personalities or more complex client setups.

    *   **`InstallOption(Enum)`**: Defines options for installing dependencies (`NEVER_INSTALL`, `INSTALL_IF_NECESSARY`, `FORCE_INSTALL`).
    *   **`ConfigTemplate`**:
        *   Represents a schema or template for configuration entries.
        *   `add_entry(entry_name, entry_value, entry_type, entry_min=None, entry_max=None, entry_help="")`: Adds a new field to the template with its type, default value, and optional constraints/help text.
    *   **`BaseConfig`**:
        *   A basic dictionary-like configuration manager.
        *   `from_template(template: ConfigTemplate, ...)`: Creates a `BaseConfig` instance from a `ConfigTemplate`.
        *   `load_config(file_path)`: Loads configuration from a YAML file.
        *   `save_config(file_path)`: Saves configuration to a YAML file.
    *   **`TypedConfig`**:
        *   Combines a `ConfigTemplate` (schema) with a `BaseConfig` (values).
        *   Enforces types and constraints defined in the template.
        *   `sync()`: Validates and updates values in the template based on the current config values, applying type conversions and constraints.

    ---

    ## 7. Types (`lollms_types.py`)

    Defines various enumerations used throughout the library.

    *   **`MSG_TYPE(Enum)`**: Specifies the type of message being communicated, especially in streaming callbacks.
        *   `MSG_TYPE_CHUNK`: A segment of a larger message.
        *   `MSG_TYPE_FULL`: A complete message.
        *   `MSG_TYPE_FULL_INVISIBLE_TO_AI`/`_USER`: Full messages with specific visibility.
        *   `MSG_TYPE_EXCEPTION`, `MSG_TYPE_WARNING`, `MSG_TYPE_INFO`: For status updates.
        *   `MSG_TYPE_STEP_START`, `MSG_TYPE_STEP_PROGRESS`, `MSG_TYPE_STEP_END`: For task progress.
        *   `MSG_TYPE_JSON_INFOS`, `MSG_TYPE_REF`, `MSG_TYPE_CODE`, `MSG_TYPE_UI`: For special content types.
        *   `MSG_TYPE_NEW_MESSAGE`, `MSG_TYPE_FINISHED_MESSAGE`: For message lifecycle.
    *   **`SENDER_TYPES(Enum)`**: Identifies the sender of a message (`USER`, `AI`, `SYSTEM`).
    *   **`SUMMARY_MODE(Enum)`**: Defines modes for text summarization (`SEQUENCIAL`, `HIERARCHICAL`).
    *   **`ELF_COMPLETION_FORMAT(Enum)`**: Specifies the type of completion expected from a model.
        *   `Instruct`: For instruction-following models (e.g., text-davinci-003).
        *   `Chat`: For chat-based models (e.g., gpt-3.5-turbo).
        *   Provides `from_string()` and `__str__` for convenience.

    ---

    ## 8. Utilities (`lollms_utilities.py`)

    Contains helper functions and classes.

    *   **`PromptReshaper`**:
        *   `__init__(template: str)`: Initializes with a prompt template containing placeholders like `{{placeholder_name}}`.
        *   `replace(placeholders: dict) -> str`: Simple placeholder replacement.
        *   `build(placeholders: dict, tokenize, detokenize, max_nb_tokens: int, place_holders_to_sacrifice: list = []) -> str`:
            Intelligently fills a prompt template, ensuring the total token count does not exceed `max_nb_tokens`. If it does, it truncates placeholders listed in `place_holders_to_sacrifice` (typically long ones like discussion history).
    *   **`encode_image(image_path, max_image_width=-1) -> str`**:
        Opens an image, optionally resizes it if `max_image_width` is set, converts to JPEG if necessary, and returns a base64 encoded string.
    *   **`discussion_path_to_url(file_path: str | Path) -> str`**: Converts a local discussion database path to a URL format relative to "discussions".
    *   **`personality_path_to_url(file_path: str | Path) -> str`**: Converts a local personality path to a URL format relative to "personalities".
    *   **`remove_text_from_string(string: str, text_to_find: str) -> str`**: Removes text from the first occurrence of `text_to_find`.
    *   **`process_ai_output(output, images, output_folder)`**: (Requires `opencv-python`) Processes LLM output that might contain bounding box information for images. Draws boxes on images and saves them. (Note: `re` module is used but not imported in the snippet; `numpy` is imported as `np` but `random_stuff = np.random` is unusual, likely meant `np.random.rand()` or similar for unique filenames).

    ---

    ## 9. Examples

    The `examples/` directory provides practical scripts demonstrating various functionalities.

    ### Article Summary (`examples/article_summary/article_summary.py`)

    Demonstrates using `LollmsClient.sequential_summarize` to summarize a document (fetched from a URL in this case). It uses `docling` to convert the URL content to markdown and then processes it chunk by chunk, extracting specific information (Title, Authors, Summary, Results) based on a detailed prompt.

    ```python
    # Key snippet from article_summary.py
    summary = lc.sequential_summarize(
        article_text,
        """
    Extract the following information if present in the chunk:
    1. **Title**: ...
    2. **Authors**: ...
    3. **Summary**: ...
    4. **Results**: ...
    Ensure that any information already in memory is retained...
    """,
        "markdown", # chunk_processing_output_format
        """Write a final markdown with these sections:
    ## Title
    ## Authors
    ## Summary
    ## Results
        """, # final_memory_processing_prompt
        # ... other parameters like ctx_size, chunk_size ...
    )
    ```

    ### Deep Analysis (`examples/deep_analyze/`)

    *   **`deep_analyse.py`**: Uses `LollmsClient.deep_analyze` to answer a question ("Explain what is the difference between HGG and QGG") based on the content of a single document (fetched from an arXiv URL).
    *   **`deep_analyze_multiple_files.py`**: Shows how to use `LollmsClient.deep_analyze` with a list of local files (PDF, TXT, MD, DOCX, etc.) found in the current directory and its subdirectories. It answers the same query based on the content of all these files.

    ```python
    # Key snippet from deep_analyse.py
    result = lc.deep_analyze(
        "Explain what is the difference between HGG and QGG",
        article_text, # or files=matching_files in the other example
        # ... other parameters ...
    )
    ```

    ### Function Calling (`examples/function_call/functions_call_with_images.py`)

    Demonstrates function calling with image input.
    1.  Defines a `capture_image` function (using `cv2`) that takes a picture from the webcam.
    2.  Registers this function with `FunctionCalling_Library`.
    3.  Prompts the LLM to look at an image and describe the user's appearance.
    4.  The LLM is expected to call `capture_image` first.
    5.  The script executes the call, then feeds the result back to the LLM for the final description.
    6.  Uses `LollmsTTS` to speak the final response.

    ```python
    # Key snippet from functions_call_with_images.py
    fcl.register_function("capture_image", capture_image, "Captures an image from the user webcam", [])
    response, function_calls = fcl.generate_with_functions_and_images(
        prompt="user: take a look at me then tell ma how i look.\nassistant: ",
        images=images, # images list is populated by capture_image
        # ...
    )
    if len(function_calls) > 0:
        results = fcl.execute_function_calls(function_calls)
        # ... feed results back to LLM ...
    ```

    ### Personality Tests (`examples/personality_test/`)

    *   **`chat_test.py`**: Creates an `LollmsPersonality` instance inline (without loading from a package) and engages in a chat loop with it using `LollmsDiscussion`.
    *   **`chat_with_aristotle.py`**: Similar to `chat_test.py`, but defines an inline personality mimicking Aristotle.
    *   **`tesks_test.py`**: Demonstrates using `TasksLibrary` methods:
        *   `multichoice_question`
        *   `yes_no`
        *   `extract_code_blocks`

    ### Local Model Testing (`examples/test_local_models/local_chat.py`)

    Shows how to use the `transformers` binding to chat with a local model (e.g., `microsoft/Phi-3-mini-4k-instruct`). It directly uses `LollmsClient.generate_text` with a formatted prompt.

    ```python
    # Key snippet from local_chat.py
    lc = LollmsClient("transformers", model_name=r"microsoft/Phi-3-mini-4k-instruct")
    out = lc.generate_text(f"{lc.system_full_header} Act as lollms, a helpful assistant.\n!@>user:Write a poem about love.\n!@>lollms:", streaming_callback=cb)
    ```

    ### Text to Audio (`examples/text_2_audio.py`)

    1.  Initializes `LollmsClient` and `LollmsTTS`.
    2.  Generates a short text ("One plus one equals ").
    3.  Uses `LollmsTTS.text2Audio()` to convert the generated text to speech using a randomly selected voice.
    4.  Also lists mounted personalities and models.

    ### Text and Image to Audio (`examples/text_and_image_2_audio.py`)

    Combines image capture, vision-language model interaction, and TTS.
    1.  Captures an image from the webcam.
    2.  Uses `LollmsClient.generate_with_images()` to get a description of the image.
    3.  Converts the description to audio using `LollmsTTS`.

    ### Text Generation (`examples/text_gen.py`)

    A basic example of text generation, similar to `text_2_audio.py` but without the TTS part. It also lists personalities and models. Allows testing different `ELF_GENERATION_FORMAT` like `OLLAMA`.

    ---

    ## 10. Code Analysis Tools

    These scripts are utilities for developers working with or on the `lollms_client` library itself, helping to generate documentation about its components.

    ### Python Analyzer (`lollms_python_analyzer.py`)

    *   Uses Python's `ast` (Abstract Syntax Tree) module to parse a Python source file.
    *   Extracts information about classes, methods (with arguments and type hints), enums, standalone functions, and dependencies (imports).
    *   Generates a Markdown file (`*_info.md`) summarizing this structure.
    *   Optionally, it can then use an `LollmsClient` instance to prompt an LLM to generate a documentation introduction based on the created Markdown summary.

    ### JavaScript Analyzer (`lollms_js_analyzer.py`)

    *   Parses a JavaScript file (line by line, with some regex-like checks).
    *   Extracts information about classes, methods, and standalone functions, including their arguments.
    *   Generates a Markdown file (`*_info.md`) with this information.
        *(Note: JavaScript parsing this way can be less robust than AST-based parsing for Python. It might struggle with complex JS syntax or unconventional formatting.)*

    ---

    ## 11. File Structure

    ```text
    📁 lollms_client/
    ├─ 📁 ai_documentation/
    │  ├─ 📄 lollms_core_classes.md  # Docs for LollmsClient
    │  ├─ 📄 lollms_tasks_classes.md   # Docs for TasksLibrary
    │  └─ 📄 README.md                 # Overview of LollmsClient (focused on core)
    ├─ 📁 examples/
    │  ├─ 📁 article_summary/
    │  │  └─ 📄 article_summary.py
    │  ├─ 📁 deep_analyze/
    │  │  ├─ 📄 deep_analyse.py
    │  │  └─ 📄 deep_analyze_multiple_files.py
    │  ├─ 📁 function_call/
    │  │  └─ 📄 functions_call_with images.py
    │  ├─ 📁 personality_test/
    │  │  ├─ 📄 chat_test.py
    │  │  ├─ 📄 chat_with_aristotle.py
    │  │  └─ 📄 tesks_test.py  # (typo, likely "tasks_test.py")
    │  ├─ 📁 test_local_models/
    │  │  └─ 📄 local_chat.py
    │  ├─ 📄 text_2_audio.py
    │  ├─ 📄 text_and_image_2_audio.py
    │  └─ 📄 text_gen.py
    ├─ 📁 lollms_client/                 # Main library code
    │  ├─ 📁 llm_bindings/              # LLM backend integrations
    │  │  ├─ 📁 lollms/
    │  │  │  └─ 📄 __init__.py         # Lollms native binding
    │  │  ├─ 📁 ollama/
    │  │  │  └─ 📄 __init__.py         # Ollama binding
    │  │  ├─ 📁 openai/
    │  │  │  └─ 📄 __init__.py         # OpenAI binding
    │  │  ├─ 📁 transformers/
    │  │  │  └─ 📄 __init__.py         # Hugging Face Transformers binding
    │  │  └─ 📄 __init__.py
    │  ├─ 📁 stt_bindings/              # Speech-to-Text bindings (currently empty)
    │  │  ├─ 📁 lollms/
    │  │  │  └─ 📄 __init__.py
    │  │  └─ 📄 __init__.py
    │  ├─ 📁 tti_bindings/              # Text-to-Image bindings (currently empty)
    │  │  ├─ 📁 lollms/
    │  │  │  └─ 📄 __init__.py
    │  │  └─ 📄 __init__.py
    │  ├─ 📁 tts_bindings/              # Text-to-Speech bindings (currently empty)
    │  │  ├─ 📁 lollms/
    │  │  │  └─ 📄 __init__.py
    │  │  └─ 📄 __init__.py
    │  ├─ 📁 ttv_bindings/              # Text-to-Video bindings (currently empty)
    │  │  ├─ 📁 lollms/
    │  │  │  └─ 📄 __init__.py
    │  │  └─ 📄 __init__.py
    │  ├─ 📄 __init__.py                 # Makes lollms_client a package, exports key classes
    │  ├─ 📄 lollms_config.py            # Configuration classes
    │  ├─ 📄 lollms_core.py              # LollmsClient class
    │  ├─ 📄 lollms_discussion.py        # LollmsDiscussion, LollmsMessage classes
    │  ├─ 📄 lollms_functions.py         # FunctionCalling_Library class
    │  ├─ 📄 lollms_js_analyzer.py       # JavaScript code analyzer tool
    │  ├─ 📄 lollms_llm_binding.py       # Base LLM binding classes
    │  ├─ 📄 lollms_personality.py       # LollmsPersonality class
    │  ├─ 📄 lollms_personality_worker.py # Worker/state machine for personalities
    │  ├─ 📄 lollms_python_analyzer.py   # Python code analyzer tool
    │  ├─ 📄 lollms_python_analyzer_info.md # Output of the python analyzer on itself
    │  ├─ 📄 lollms_stt.py               # LollmsSTT client class
    │  ├─ 📄 lollms_tasks.py             # TasksLibrary class
    │  ├─ 📄 lollms_tasks_info.md        # Output of python analyzer on lollms_tasks.py
    │  ├─ 📄 lollms_tti.py               # LollmsTTI client class (misnamed in tree, likely LollmsTTI)
    │  ├─ 📄 lollms_tts.py               # LollmsTTS client class
    │  ├─ 📄 lollms_types.py             # Enum types
    │  └─ 📄 lollms_utilities.py         # Utility functions
    ├─ 📄 CHANGELOG.md
    ├─ 📄 README.md                     # Project README
    ├─ 📄 requirements.txt
    └─ 📄 setup.py
    ```

    ---

    ## 12. Changelog

    *   **v 0.10.0 (from setup.py)**
    *   **v 0.6.0:** Added function calls
    *   **v 0.0.7:** Added listMountedPersonalities

    ---

    ## 13. Dependencies

    As listed in `requirements.txt`:

    *   `requests>=2.25.1`
    *   `ascii-colors`
    *   `pillow`
    *   `pipmaster`
    *   `yaml`
    *   `tiktoken` (for OpenAI binding)
    *   `pydantic`
    *   `lollmsvectordb`
    *   `numpy`

    Additional implicit dependencies for specific bindings:
    *   `openai` (for OpenAI binding)
    *   `torch`, `transformers` (for Transformers binding)
    *   `opencv-python` (for `lollms_utilities.process_ai_output`)
    *   `docling` (for `examples/article_summary/` and `examples/deep_analyze/`)

    ---

    ## 14. License

    The `lollms_client` library is distributed under the Apache Software License 2.0.
    (As indicated in `setup.py`)

    ---
    ## 15. External Documentation: `ascii_colors`

    The `lollms_client` library uses `ascii_colors` for console output styling and logging.
    Full documentation for `ascii_colors` can be found at: [ASCIIColors Documentation](https://parisneo.github.io/ascii_colors/)

    (The content of `ascii_colors.md` would be inserted here as provided in the prompt.)

    ---
    **Documentation: `ascii_colors.md`**

    # ASCIIColors: Rich Logging, Colors, Progress Bars & Menus - All In One! 🎨🪵📊 interactive

    [![PyPI version](https://img.shields.io/pypi/v/ascii_colors.svg)](https://pypi.org/project/ascii-colors/)
    [![PyPI pyversions](https://img.shields.io/pypi/pyversions/ascii_colors.svg)](https://pypi.org/project/ascii-colors/)
    [![PyPI license](https://img.shields.io/pypi/l/ascii_colors.svg)](https://github.com/ParisNeo/ascii_colors/blob/main/LICENSE)
    [![PyPI downloads](https://img.shields.io/pypi/dm/ascii_colors.svg)](https://pypi.org/project/ascii-colors/)
    [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
    [![Documentation Status](https://parisneo.github.io/ascii_colors/badge/?version=latest)](https://parisneo.github.io/ascii_colors/)

    ---

    **Stop wrestling with multiple libraries for essential CLI features!**

    **ASCIIColors** is your unified toolkit for creating modern, engaging, and informative Python terminal applications. Forget bland `print()` statements and complex logging setups. Embrace vibrant colors, structured logging, sleek progress bars, interactive menus, and helpful utilities – all from a single, elegant library.

    ## Simple colorful and stylish printing
    ![](assets/colors_and_styles.png)

    ## Complete logging system fully compatible with python logging library
    ![](assets/logging.png)

    ## Full Menu management system
    ![](assets/ascii_menu.gif)

    ## TQDM like colorful progressbars
    ![](assets/ascii_progress_animation.gif)

    ## User interaction utilities
    ![](assets/confirm_prompt.png)

    ---

    ## ✨ Why Choose ASCIIColors?

    *   🎨 **Dual Approach:** Seamlessly switch between simple, direct color printing for immediate feedback and a powerful, structured logging system for application events.
    *   🪵 **Logging Powerhouse:** Get instantly colored, leveled console logs (`stderr` default) with `basicConfig`. Easily configure file logging, JSON output, log rotation, custom formats, and context injection. Features a **`logging`-compatible API** (`getLogger`, `basicConfig`, Handlers) for painless adoption.
    *   📊 **Integrated Progress Bars:** Display `tqdm`-like progress bars for loops or tasks with customizable styles (`fill`, `blocks`, `line`, `emoji`) and colors, directly integrated.
    *   🖱️ **Interactive Menus:** Build intuitive, visually styled command-line menus with arrow-key navigation, different selection modes (`execute`, `select_single`, `select_multiple`), filtering, inline input fields, help text, and submenus.
    *   🤝 **User Interaction:** Easily prompt users for text input (with optional hidden input for passwords) and ask for yes/no confirmation using `prompt()` and `confirm()`.
    *   ⚙️ **Utilities Included:** Comes with `execute_with_animation` (console spinner), `highlight` (text emphasis), `multicolor` (inline colored text), and `trace_exception` (easy error logging).
    *   🚀 **Simplify Your Stack:** Reduce project dependencies and complexity by using one library for colors, logging, progress bars, menus, and basic user interaction.
    *   ✅ **Effortless Integration:** Use the familiar `import ascii_colors as logging` pattern or the native `ASCIIColors` API. Direct print methods remain independent for simple use cases.

    ---

    ## 🚀 Installation

    ```bash
    pip install ascii_colors
    ```
    *(Optional: For accurate wide-character support (like emojis) in ProgressBar, install `wcwidth`: `pip install wcwidth`)*

    ---

    ## 📚 Core Concepts: Direct Print vs. Logging System

    Understanding this difference is fundamental:

    1.  **Direct Print Methods (`ASCIIColors.red`, `print`, `bold`, `bg_red`, `prompt`, `confirm`, etc.):**
        *   **Mechanism:** Use Python's `print()` (or `input`/`getpass`) to **directly** interact with the terminal (default: `sys.stdout`/`stdin`). Outputs strings with specified ANSI colors/styles.
        *   **Scope:** **Completely bypasses** the logging system. Levels, Handlers, Formatters, Context are **ignored**.
        *   **Use Case:** Ideal for immediate visual feedback, status messages, banners, prompts, user input/confirmation, menus, progress bars, animations, or decorative output where structured logging features aren't necessary.

    2.  **Logging System (`basicConfig`, `getLogger`, `logger.info`, `ASCIIColors.info`, Handlers, Formatters):**
        *   **Mechanism:** Creates structured log records, filters them by level, formats them into strings using `Formatters`, and dispatches them via `Handlers` to destinations (console, file, etc.). Mimics Python's standard `logging` module.
        *   **Scope:** Provides leveled logging, output routing, filtering, contextual information, and flexible formatting. Console output is typically colored by log level.
        *   **Interaction:** Use `import ascii_colors as logging` (recommended) or `ASCIIColors.info()` methods. Both control the *same* global logging state.
        *   **Use Case:** Best for application logs, debugging, tracing events, audit trails – any scenario needing structured, configurable, and routable output.

    *Utility Interactions:* `highlight`, `multicolor`, `execute_with_animation`, `Menu`, `ProgressBar`, `confirm`, and `prompt` use **Direct Printing** for their visual output/interaction. `trace_exception` uses the **Logging System**.

    ---

    ## 🎨 Direct Printing In-Depth

    Instantly add color and style to terminal output.

    ### Basic Usage

    Call static methods on `ASCIIColors` for specific colors or styles.

    ```python
    from ascii_colors import ASCIIColors

    ASCIIColors.red("Error: File processing failed.")
    ASCIIColors.green("Success: Data saved.")
    ASCIIColors.yellow("Warning: Using default value.")
    ASCIIColors.blue("Info: Connecting to server...")
    ASCIIColors.bold("This is important!")
    ASCIIColors.underline("Please read the instructions.")
    ASCIIColors.italic("Note: This is experimental.", color=ASCIIColors.color_magenta) # Combine style method with color arg
    ```

    ### Advanced Usage with `ASCIIColors.print()`

    The core direct print method offers full control.

    ```python
    from ascii_colors import ASCIIColors
    import sys

    # Syntax: print(text, color=..., style=..., background=..., end=..., flush=..., file=...)

    ASCIIColors.print(
        " Detailed Status ",
        color=ASCIIColors.color_black,           # Foreground color constant
        style=ASCIIColors.style_bold,            # Style constant
        background=ASCIIColors.color_bg_cyan,    # Background color constant
        end="\n\n",                              # Custom line ending
        flush=True,                              # Force flush buffer
        file=sys.stdout                          # Specify output stream
    )

    # Combine multiple styles
    combined_style = ASCIIColors.style_bold + ASCIIColors.style_underline + ASCIIColors.style_italic
    ASCIIColors.print(
        "Multi-styled Text",
        color=ASCIIColors.color_bright_white,
        style=combined_style
    )
    ```

    ### Available Colors & Styles Constants

    Access these as `ASCIIColors.<constant_name>`:

    *   **Reset:** `color_reset` (resets all)
    *   **Styles:**
        *   `style_bold`
        *   `style_dim`
        *   `style_italic`
        *   `style_underline`
        *   `style_blink` (support varies)
        *   `style_reverse` (swaps foreground/background)
        *   `style_hidden` (support varies)
        *   `style_strikethrough`
    *   **Foreground (Regular):** `color_black`, `color_red`, `color_green`, `color_yellow`, `color_blue`, `color_magenta`, `color_cyan`, `color_white`, `color_orange` (256-color)
    *   **Foreground (Bright):** `color_bright_black` (gray), `color_bright_red`, `color_bright_green`, `color_bright_yellow`, `color_bright_blue`, `color_bright_magenta`, `color_bright_cyan`, `color_bright_white`
    *   **Background (Regular):** `color_bg_black`, `color_bg_red`, `color_bg_green`, `color_bg_yellow`, `color_bg_blue`, `color_bg_magenta`, `color_bg_cyan`, `color_bg_white`, `color_bg_orange` (256-color)
    *   **Background (Bright):** `color_bg_bright_black` (gray), `color_bg_bright_red`, `color_bg_bright_green`, `color_bg_bright_yellow`, `color_bg_bright_blue`, `color_bg_bright_magenta`, `color_bg_bright_cyan`, `color_bg_bright_white`

    *(Note: Rendering depends on terminal emulator capabilities.)*

    ### Inline Multicolor Text (`multicolor`)

    Print segments with different styles on the same line.

    ```python
    from ascii_colors import ASCIIColors

    ASCIIColors.multicolor(
        # List of text segments
        ["Processing: ", "FileA.txt", " [", "OK", "] ", "Size: ", "1.2MB"],
        # Corresponding list of color/style constants
        [
            ASCIIColors.color_white,              # "Processing: "
            ASCIIColors.color_cyan,               # "FileA.txt"
            ASCIIColors.color_white,              # " ["
            ASCIIColors.color_green + ASCIIColors.style_bold, # "OK" (bold green)
            ASCIIColors.color_white,              # "] "
            ASCIIColors.color_white,              # "Size: "
            ASCIIColors.color_yellow              # "1.2MB"
        ]
    )
    # Output: Processing: FileA.txt [OK] Size: 1.2MB (with styles applied)
    ```

    ### Highlighting Substrings (`highlight`)

    Emphasize parts of a string.

    ```python
    from ascii_colors import ASCIIColors

    log_entry = "ERROR: Failed login attempt for user 'admin' from IP 192.168.1.101"

    ASCIIColors.highlight(
        text=log_entry,
        subtext=["ERROR", "admin", "192.168.1.101"], # String or list of strings to find
        color=ASCIIColors.color_white,             # Default text color
        highlight_color=ASCIIColors.color_bright_yellow + ASCIIColors.style_underline, # Style for matches
        # whole_line=True                          # Set True to highlight the entire line if a match is found
    )
    # Output: ERROR: Failed login attempt for user 'admin' from IP 192.168.1.101
    #         ^^^^^                               ^^^^^          ^^^^^^^^^^^^^^^ (highlighted)
    ```

    ### Persistent Styles (`activate`/`reset`)

    Apply a style that stays active until reset (less common, use `print` usually).

    ```python
    from ascii_colors import ASCIIColors

    ASCIIColors.activate(ASCIIColors.color_blue + ASCIIColors.style_italic)
    print("This text will be blue and italic.")
    print("This text will also be blue and italic.")
    ASCIIColors.reset() # Reset to terminal default
    print("This text is back to normal.")
    ```

    ---

    ## 🪵 Logging System In-Depth

    Build robust, structured, and configurable logs.

    ### The Compatibility Layer (`import ascii_colors as logging`)

    **This is the recommended way to use the logging system.** It provides a familiar interface.

    ```python
    import ascii_colors as logging # The key alias!

    # Configure using basicConfig
    logging.basicConfig(level=logging.INFO)

    # Get and use loggers
    logger = logging.getLogger("MyService")
    logger.info("Service started.")
    ```

    ### Configuration with `basicConfig()`

    The easiest way to set up basic logging. **Call it only once** at application start (unless `force=True`).

    **Common Parameters:**

    *   `level`: Minimum level for the root logger (and default handlers). E.g., `logging.DEBUG`, `"INFO"`, `30`. Default: `WARNING`.
    *   `format` (or `fmt`): Log message format string (see [Formatter Placeholders](#-formatter-placeholders)). Default: `%(levelname)s:%(name)s:%(message)s` (uses `%` style).
    *   `datefmt`: Format string for `%(asctime)s`. Default: ISO-like `"%Y-%m-%d %H:%M:%S,%f"`.
    *   `style`: Format string style (`'%'` or `'{'`). Default: `'%'`.
    *   `stream`: Target stream for the default `ConsoleHandler` (e.g., `sys.stdout`). Default: `sys.stderr`. Ignored if `filename` or `handlers` is used.
    *   `filename`: Path to log file. Creates a `FileHandler`. Incompatible with `stream` or `handlers`.
    *   `filemode`: File open mode (`'a'` append, `'w'` write). Default: `'a'`. Requires `filename`.
    *   `encoding`: File encoding (e.g., `'utf-8'`). Requires `filename`.
    *   `handlers`: A list of pre-configured handler instances. If provided, `stream` and `filename` are ignored.
    *   `force`: If `True`, removes existing handlers before configuring. Allows calling `basicConfig` multiple times. Default: `False`.

    **Examples:**

    ```python
    import ascii_colors as logging
    from pathlib import Path
    import sys

    # Example 1: Simple colored console logging (INFO+) to stdout
    # logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='[%(levelname)s] %(message)s')

    # Example 2: Log DEBUG+ to a file, overwrite on start
    # log_file = Path("app.log")
    # logging.basicConfig(level=logging.DEBUG, filename=log_file, filemode='w',
    #                     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Example 3: Log INFO+ to console (stderr) AND DEBUG+ to a file
    log_file = Path("app_combined.log")
    # Configure console handler via basicConfig
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    # Manually create and add file handler
    file_formatter = logging.Formatter('%(asctime)s | %(message)s')
    file_handler = logging.FileHandler(log_file, level=logging.DEBUG, formatter=file_formatter)
    logging.getLogger().addHandler(file_handler) # Add to root logger

    logger = logging.getLogger("Combined")
    logger.info("Goes to console and file.")
    logger.debug("Goes to file only.")
    ```

    ### Manual Configuration (Full Control)

    For complex scenarios involving multiple handlers, specific formatters, or fine-grained control.

    **Steps:**

    1.  **Get Logger:** `logger = logging.getLogger("MyComponent")` (Use names like `parent.child` for hierarchy).
    2.  **Create Formatter(s):**
        *   `fmt = logging.Formatter(fmt=..., datefmt=..., style=..., include_source=...)`
        *   `json_fmt = logging.JSONFormatter(fmt=..., datefmt=..., style=..., include_fields=..., ...)`
    3.  **Create Handler(s):**
        *   `con_h = logging.ConsoleHandler(stream=..., level=..., formatter=...)` (or `StreamHandler`)
        *   `file_h = logging.FileHandler(filename=..., mode=..., encoding=..., level=..., formatter=...)`
        *   `rot_h = logging.handlers.RotatingFileHandler(filename=..., maxBytes=..., backupCount=..., level=..., formatter=...)`
    4.  **Add Handlers to Logger:** `logger.addHandler(handler_instance)` (or add to root logger `logging.getLogger().addHandler(...)` to affect all loggers).
    5.  **Set Logger Level (Optional):** `logger.setLevel(logging.DEBUG)` (Controls messages passed *from this logger* to its handlers. Global level `ASCIIColors.set_log_level` filters *before* any logger).

    **Example:**

    ```python
    import ascii_colors as logging
    from ascii_colors import handlers # Access RotatingFileHandler
    from pathlib import Path
    import sys

    # --- Get Loggers ---
    root_logger = logging.getLogger() # Configure root for global effect
    module_logger = logging.getLogger("MyModule")

    # --- Set Levels ---
    # Global filter: Allow DEBUG and above to reach loggers
    logging.ASCIIColors.set_log_level(logging.DEBUG)
    # Root logger filter: Allow INFO and above to pass to its handlers
    root_logger.setLevel(logging.INFO)

    # --- Create Formatters ---
    console_format = "[{levelname:<8}] {message} ({name})"
    console_fmt = logging.Formatter(console_format, style='{', datefmt='%H:%M:%S')

    file_format = "%(asctime)s|%(levelname)-8s|%(name)s:%(lineno)d|%(message)s"
    file_fmt = logging.Formatter(file_format, style='%', include_source=True) # Include source info

    # --- Create Handlers ---
    console_handler = logging.ConsoleHandler(stream=sys.stdout, level=logging.INFO) # INFO+
    console_handler.setFormatter(console_fmt)

    file_handler = logging.FileHandler("manual_app.log", mode='w', level=logging.DEBUG) # DEBUG+
    file_handler.setFormatter(file_fmt)

    # --- Add Handlers to Root Logger ---
    # Clear previous handlers if re-configuring
    root_logger.handlers.clear() # Or use basicConfig(force=True) initially
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # --- Log Messages ---
    module_logger.info("Module starting.") # Goes to console & file
    module_logger.debug("Low-level details.") # Goes to file only (filtered by console handler level)
    ```

    ### Formatter Placeholders

    Use these within `format` strings (`fmt` parameter):

    *   **`%` Style (Default):**
        *   `%(asctime)s`: Human-readable time (configured by `datefmt`).
        *   `%(created)f`: Time of creation (float, `time.time()`).
        *   `%(filename)s`: Filename part of pathname. Requires `include_source=True`.
        *   `%(funcName)s`: Name of function containing the log call. Requires `include_source=True`.
        *   `%(levelname)s`: Text logging level ('DEBUG', 'INFO', etc.).
        *   `%(levelno)s`: Numeric logging level (10, 20, etc.).
        *   `%(lineno)d`: Line number where log call occurs. Requires `include_source=True`.
        *   `%(message)s`: The logged message itself.
        *   `%(module)s`: Module name (filename without extension). Requires `include_source=True`.
        *   `%(msecs)d`: Millisecond portion of timestamp.
        *   `%(name)s`: Name of the logger used.
        *   `%(pathname)s`: Full path to the source file. Requires `include_source=True`.
        *   `%(process)d`: Process ID.
        *   `%(processName)s`: Process name (usually Python thread name).
        *   `%(relativeCreated)d`: Time in milliseconds since logger initialized.
        *   `%(thread)d`: Thread ID.
        *   `%(threadName)s`: Thread name.
        *   `%(<custom_key>)s`: Any key passed via `extra={...}` or context.
    *   **`{}` Style:** Use the same names within braces, e.g., `{asctime}`, `{levelname}`, `{name}`, `{message}`, `{filename}`, `{lineno}`, `{funcName}`, `{custom_key}`.

    **Note:** Retrieving `filename`, `pathname`, `lineno`, `funcName`, `module` requires setting `include_source=True` on the `Formatter`, which adds performance overhead due to stack inspection.

    ### JSON Formatter (`JSONFormatter`)

    Log structured JSON, ideal for log aggregation systems.

    ```python
    import ascii_colors as logging
    from pathlib import Path

    log_file = Path("audit.jsonl")

    # Configure JSON Formatter
    json_formatter = logging.JSONFormatter(
        # Option 1: Define exact output structure with fmt dict (values are format strings)
        fmt={
            "ts": "%(asctime)s",
            "lvl": "%(levelname)s",
            "log": "%(name)s",
            "msg": "%(message)s",
            "ctx": { # Nested context example
                "request": "%(request_id)s",
                "user": "%(user_id)s",
                "file": "%(filename)s" # Requires include_source=True if using this
            },
            "exc_info": "%(exc_info)s" # Include formatted exception string if present
        },
        # Option 2: Alternatively, select standard fields to include
        # include_fields=["asctime", "levelname", "name", "message", "user_id", "request_id", "exc_info", "exc_type"],
        datefmt="iso",         # Use ISO 8601 timestamps
        style='%',             # Style for resolving format strings in fmt dict
        json_ensure_ascii=False, # Allow UTF-8 characters
        json_indent=None,      # Set to integer (e.g., 2) for pretty-printing (usually None for log files)
        json_sort_keys=False,  # Preserve order from fmt dict if possible
        include_source=True    # Needed if format strings reference source info
    )

    # Setup handler using the JSON formatter
    json_handler = logging.FileHandler(log_file, mode='w')
    json_handler.setFormatter(json_formatter)

    logging.basicConfig(level=logging.INFO, handlers=[json_handler], force=True) # Use only this handler

    logger = logging.getLogger("API")
    try:
        1 / 0
    except Exception as e:
        # Pass context via 'extra' and include exception info
        logger.error("Processing failed for request.",
                    extra={"user_id": "usr_456", "request_id": "req_xyz"},
                    exc_info=True) # Logs the exception details

    # Log file 'audit.jsonl' will contain a JSON object per line (JSON Lines format)
    ```

    ### Logging Messages & Exceptions

    Use standard logger methods.

    ```python
    import ascii_colors as logging
    from ascii_colors import trace_exception # Utility function

    logging.basicConfig(level=logging.DEBUG) # Basic setup
    logger = logging.getLogger("Processor")

    # Standard levels
    logger.debug("Starting step %d...", 1)
    logger.info("Processing record %s.", "ID-001")
    logger.warning("Timeout occurred for %s.", "ID-002")
    logger.error("Failed to write output for %s.", "ID-003")
    logger.critical("System integrity check failed!")

    # Logging with %-style arguments
    logger.info("User %s performed action %s on resource %d.", "admin", "UPDATE", 42)

    # Logging exceptions
    try:
        result = 1 / 0
    except ZeroDivisionError as e:
        # Option 1: logger.exception (in except block) - logs at ERROR level
        logger.exception("Arithmetic error during calculation for ID %s.", "ID-004")
        # Option 2: logger.error with exc_info=True
        # logger.error("Arithmetic error occurred", exc_info=True)
        # Option 3: trace_exception utility (logs at ERROR level)
        # trace_exception(e)
    ```

    ### Context Management (Thread-Local)

    Enrich logs automatically with contextual data relevant to the current thread or task.

    1.  **Set Context:**
        *   `ASCIIColors.set_context(key1=value1, key2=value2)`: Sets context for the current thread.
        *   `with ASCIIColors.context(key1=value1, key2=value2): ...`: Sets context only within the `with` block. Automatically restores previous state on exit.
    2.  **Configure Formatter:** Ensure your `Formatter` includes the context keys (e.g., `%(request_id)s` or `{request_id}`).
    3.  **Log:** Messages logged within the context scope will include the values.

    ```python
    from ascii_colors import ASCIIColors, Formatter, ConsoleHandler, getLogger, INFO
    import threading, time, sys

    # Formatter includes context keys 'req_id' and 'user'
    fmt_string = "[{asctime}] Req:{req_id}|User:{user} [{levelname}] {message}"
    formatter = Formatter(fmt_string, style='{', datefmt='%H:%M:%S')
    handler = ConsoleHandler(stream=sys.stdout, formatter=formatter)
    # Apply setup (clearing previous handlers for clarity)
    ASCIIColors.clear_handlers(); ASCIIColors.add_handler(handler); ASCIIColors.set_log_level(INFO)
    logger = getLogger("ContextDemo")

    def handle_request(request_id, user_name):
        # Use context manager for automatic cleanup
        with ASCIIColors.context(req_id=request_id, user=user_name):
            logger.info("Request received")
            # Simulate work
            time.sleep(0.05)
            logger.info("Processing complete")

    # Simulate concurrent requests
    threads = [
        threading.Thread(target=handle_request, args=(f"R{i}", f"User{i}")) for i in range(3)
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    # Output will automatically include the correct req_id and user for each log line
    ```
    You can retrieve the current context dictionary using `ASCIIColors.get_thread_context()`.

    ---

    ## 📊 Progress Bar (`ProgressBar`)

    Display `tqdm`-like progress indicators. Uses **Direct Printing**.

    **Key Parameters:**

    *   `iterable`: Optional iterable to wrap (like `tqdm(iterable)`).
    *   `total`: Total number of expected iterations (required if `iterable` has no `len`).
    *   `desc`: String description prefix.
    *   `unit`: Label for iterations (default: "it").
    *   `ncols`: Fixed width for the entire bar; `None` for auto-detect.
    *   `bar_format`: Custom format string. Use placeholders like `{l_bar}`, `{bar}`, `{r_bar}`, `{n_fmt}`, `{total_fmt}`, `{percentage}`, `{elapsed}`, `{remaining}`, `{rate_fmt}`. For indeterminate bars (no total), only `{l_bar}`, `{bar}`, `{n}`, `{elapsed}`, `{rate_fmt}`, `{unit}` are reliably substituted.
    *   `leave`: Keep the completed bar on screen (`True`) or clear it (`False`). Default: `True`.
    *   `mininterval`: Minimum time in seconds between display updates. Default: `0.1`.
    *   `color`, `style`, `background`: `ASCIIColors` constants for bar/text styling.
    *   `bar_style`: `'fill'` (default, solid block), `'blocks'` (smoother Unicode blocks), `'line'` (growing line), `'emoji'` (uses custom chars).
    *   `progress_char`, `empty_char`: Characters for filled/empty parts. Ignored for `'emoji'`. Defaults vary by `bar_style`.
    *   `emoji_fill`, `emoji_empty`: Characters used for `'emoji'` style (defaults: 😊, 😞).

    **Examples:**

    ```python
    from ascii_colors import ProgressBar, ASCIIColors
    import time

    # --- Example 1: Wrapping an iterable ('fill' style) ---
    items = range(200)
    print("Wrapping an iterable:")
    for item in ProgressBar(items, desc="Processing", unit=" tasks", color=ASCIIColors.color_green):
        time.sleep(0.01)

    # --- Example 2: Manual control, 'blocks' style ---
    print("\nManual control ('blocks' style):")
    total_size = 500
    with ProgressBar(total=total_size, desc="Downloading", unit=" KB",
                    color=ASCIIColors.color_bright_blue, style=ASCIIColors.style_bold,
                    bar_style="blocks", # Use smooth block style
                    mininterval=0.05) as pbar:
        for i in range(total_size):
            time.sleep(0.005)
            pbar.update(1) # Increment progress
            if i == total_size // 2:
                pbar.set_description("Half done...") # Update description dynamically

    # --- Example 3: 'line' style ---
    print("\n'line' style:")
    for item in ProgressBar(range(100), desc="Line Task", bar_style='line', color=ASCIIColors.color_magenta):
        time.sleep(0.015)

    # --- Example 4: 'emoji' style ---
    print("\n'emoji' style:")
    for item in ProgressBar(range(60), desc="Rockets", bar_style='emoji',
                            emoji_fill="🚀", emoji_empty="🌑"):
        time.sleep(0.03)

    # --- Example 5: Indeterminate (no total) ---
    print("\nIndeterminate style:")
    with ProgressBar(desc="Waiting...", color=ASCIIColors.color_yellow) as pbar:
        for _ in range(5):
            time.sleep(0.5)
            pbar.update(10) # Can still track counts
    ```

    ---

    ## 🖱️ Interactive Menu (`Menu`)

    Build styled CLI menus with arrow-key navigation, different modes, filtering, and input. Uses **Direct Printing**.

    **Key `Menu` Parameters:**

    *   `title`: Menu title.
    *   `parent`: Link to parent `Menu` for 'Back' navigation.
    *   `mode`: `'execute'` (run actions), `'select_single'` (return one value), `'select_multiple'` (return list of values). Default: `'execute'`.
    *   `clear_screen_on_run`: Clear terminal before showing (`True`).
    *   `hide_cursor`: Attempt to hide cursor during interaction (`True`).
    *   `enable_filtering`: Allow typing to filter items (`False`).
    *   `help_area_height`: Number of lines reserved below menu for help text (`0`).
    *   Styling: `title_color`, `item_color`, `selected_color`, `selected_background`, `prompt_color`, `error_color`, `filter_color`, `help_color`, etc.
    *   Prefixes: `selected_prefix`, `unselected_prefix`, `checkbox_selected`, etc.

    **Adding Items:**

    *   `.add_action(text, function, *, value=None, exit_on_success=False, item_color=None, help_text=None, disabled=False)`
    *   `.add_submenu(text, submenu_instance, *, value=None, item_color=None, help_text=None, disabled=False)`
    *   `.add_choice(text, *, value=None, selected=False, item_color=None, help_text=None, disabled=False)`: For use in `select_single`/`select_multiple` modes.
    *   `.add_input(text, *, initial_value="", placeholder="{input}", value=None, item_color=None, help_text=None, disabled=False)`: Inline text input.
    *   `.add_separator(text=None)`

    **Navigation & Interaction:**

    *   **Arrows Up/Down:** Move selection.
    *   **Enter:**
        *   Execute action or enter submenu (in `execute` mode).
        *   Select item and exit menu (in `select_single` mode).
        *   Toggle item selection (in `select_multiple` mode - see Note below).
        *   Start editing input field.
    *   **Space:** Toggle item selection (in `select_multiple` mode).
    *   **Typing (if `enable_filtering=True`):** Filters the list of items. `Backspace` removes characters from filter.
    *   **Ctrl+C:** Quit main menu, or go back in submenu.
    *   **Input Field Editing:** Use `Left`/`Right`/`Backspace`/`Printable Keys`. `Enter`/`Escape` finishes editing.

    *Note on Multi-Select Enter:* By default, Enter toggles items in `select_multiple` mode. If you add an `action` to a choice in multi-select, Enter will *execute* that action instead of toggling. Use Spacebar for toggling in those cases.

    **Example:**

    ```python
    from ascii_colors import Menu, MenuItem, ASCIIColors
    import platform, time

    def action_ok(): ASCIIColors.green("Action OK!")
    def action_exit_success(): ASCIIColors.success("Exiting Menu!"); return True # Causes menu exit

    # --- Menus ---
    root = Menu("Unified CLI Menu", enable_filtering=True, help_area_height=2)
    single_sel = Menu("Select Format", parent=root, mode='select_single')
    multi_sel = Menu("Select Features", parent=root, mode='select_multiple')

    # --- Root Items ---
    root.add_action("Show Platform", lambda: ASCIIColors.info(f"OS: {platform.system()}"),
                    help_text="Display the current operating system.")
    root.add_submenu("Choose Format", single_sel, help_text="Select one output format.")
    root.add_submenu("Configure Features", multi_sel, help_text="Toggle multiple features (Spacebar).")
    root.add_action("Action That Exits", action_exit_success, exit_on_success=True,
                    help_text="This action will close the menu if it succeeds.")
    root.add_separator()
    root.add_input("Enter Username: ", initial_value="guest", help_text="Type a username here.")
    root.add_action("Disabled Action", action_ok, disabled=True)

    # --- Submenu Items ---
    single_sel.add_choice("Text", value="txt", help_text="Plain text format.")
    single_sel.add_choice("JSON", value="json", help_text="JSON format.")
    single_sel.add_choice("YAML", value="yaml", disabled=True)

    multi_sel.add_choice("Verbose Logging", value="VERBOSE", selected=True)
    multi_sel.add_choice("Auto Save", value="AUTOSAVE")
    multi_sel.add_choice("Notifications", value="NOTIFY", selected=True)

    # --- Run ---
    ASCIIColors.print("\nStarting interactive menu demo (Arrows, Enter, Space, Type to filter, Ctrl+C)...\n", color=ASCIIColors.color_yellow)
    result = root.run() # Run the main menu

    ASCIIColors.print("\n--- Menu Result ---", color=ASCIIColors.color_bright_white)
    if isinstance(result, list):
        ASCIIColors.print(f"Multi-select returned: {result}", color=ASCIIColors.color_green)
    elif result is not None:
        ASCIIColors.print(f"Single-select or Exit Action returned: {result}", color=ASCIIColors.color_cyan)
    else:
        ASCIIColors.print("Menu exited (Quit/Back/Execute mode completed).", color=ASCIIColors.color_yellow)

    # Access input value after run (find the item by text or other means)
    input_item = next((item for item in root.items if item.is_input), None)
    if input_item:
        ASCIIColors.print(f"Username entered was: '{input_item.input_value}'", color=ASCIIColors.color_magenta)

    ```

    ---

    ## ⏳ Animation Spinner (`execute_with_animation`)

    Provide visual feedback during blocking operations. Uses **Direct Printing**.

    **Key Parameters:**

    *   `pending_text`: Text displayed next to the spinner.
    *   `func`: The function/callable to execute while the spinner runs.
    *   `*args`, `**kwargs`: Arguments passed to `func`.
    *   `color`: Optional `ASCIIColors` color constant for the `pending_text`.

    **How it Works:**

    1.  Displays `pending_text` and an animated spinner (using direct print).
    2.  Runs `func(*args, **kwargs)` in a separate thread.
    3.  *Logging within `func` uses the configured Logging System normally.*
    4.  When `func` finishes:
        *   Stops the spinner.
        *   Prints a final status line (✓ for success, ✗ for failure) using direct print.
        *   Returns the result of `func`.
        *   If `func` raised an exception, `execute_with_animation` re-raises it.

    **Example:**

    ```python
    from ascii_colors import ASCIIColors, trace_exception
    import time
    import ascii_colors as logging # For logging inside the task

    logging.basicConfig(level=logging.INFO, format='>> %(message)s') # Configure logging

    def simulate_api_call(endpoint):
        logger = logging.getLogger("APICall")
        logger.info(f"Calling endpoint: {endpoint}") # Log inside the task
        time.sleep(2)
        if endpoint == "fail":
            raise ConnectionError("Could not connect to API")
        return {"status": "OK", "data": [1, 2, 3]}

    print("\nExecuting task with spinner:")
    try:
        result = ASCIIColors.execute_with_animation(
            "Calling API...", simulate_api_call, "users", # args for simulate_api_call
            color=ASCIIColors.color_bright_magenta
        )
        ASCIIColors.success(f"API Call Successful: {result}") # Use direct print for overall status
    except Exception as e:
        ASCIIColors.fail(f"API Call Failed: {e}")
        # Optionally log the failure again using the logging system
        # trace_exception(e)
    ```

    ---
    ## 🤝 User Interaction (`confirm` / `prompt`)

    Easily get confirmations or text input from the user directly in the terminal. These methods use **Direct Printing** for the prompts.

    *   **`ASCIIColors.confirm(question, default_yes=None, ...)`**: Asks a Yes/No question.
        *   Handles `y/yes` and `n/no` (case-insensitive).
        *   `default_yes=True`: Enter defaults to Yes (`[Y/n]`).
        *   `default_yes=False`: Enter defaults to No (`[y/N]`).
        *   `default_yes=None`: Enter is invalid (`[y/n]`).
        *   Returns `True` for Yes, `False` for No (or Ctrl+C).

    *   **`ASCIIColors.prompt(prompt_text, color=..., style=..., hide_input=False, ...)`**: Displays a styled prompt and reads a line of text.
        *   Returns the user's input string.
        *   Returns an empty string if cancelled with Ctrl+C.
        *   `hide_input=True`: Don't echo input characters (uses `getpass`).

    ```python
    from ascii_colors import ASCIIColors

    # --- Confirmation Examples ---
    delete_it = ASCIIColors.confirm("Are you sure you want to delete the file?", default_yes=False)
    if delete_it:
        print("Deleting...")
    else:
        print("Deletion cancelled.")

    proceed = ASCIIColors.confirm("Continue with installation?", default_yes=True)


    # --- Prompt Examples ---
    name = ASCIIColors.prompt("Enter your name: ", color=ASCIIColors.color_cyan)
    api_key = ASCIIColors.prompt(
        "Enter your API key: ",
        color=ASCIIColors.color_yellow,
        style=ASCIIColors.style_bold,
        hide_input=True # Hide the input
    )
    if api_key:
        print("API Key received.")
    else:
        # Could be empty input or Ctrl+C
        print("API Key entry skipped or cancelled.")
    ```

    ---

    ## 📚 API & Documentation

    This README covers the primary functionalities. For a complete API reference and further details, please visit the **[Full Documentation](https://parisneo.github.io/ascii_colors/)**.

    ---

    ## 🤝 Contributing

    Your contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting issues, proposing features, and submitting pull requests.

    ---

    ## 📜 License

    ASCIIColors is distributed under the Apache License 2.0. See the [LICENSE](LICENSE) file for more information.

    ---

    **Elevate your command-line applications. Choose `ascii_colors` for a unified, powerful, and visually appealing experience!**
    ---
