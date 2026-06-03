<<<<<<< SEARCH
        if choice == "1":
            # --- SECTION 1: LLM BINDING ---
            available_llms = []
            if llm_bindings_dir.exists():
                available_llms = [d.name for d in llm_bindings_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
            if not available_llms:
                available_llms = ["ollama", "openai", "open_router", "claude", "gemini", "litellm", "vllm"]

            print("\nSelect LLM Binding Provider:")
            for idx, binding in enumerate(available_llms):
                print(f"  [{idx + 1}] {binding}")

            llm_choice = input(f"Enter selection number [Current: {cfg.get('llm_binding_name')}]: ").strip()
            if llm_choice:
                try:
                    idx = int(llm_choice) - 1
                    if 0 <= idx < len(available_llms):
                        cfg["llm_binding_name"] = available_llms[idx]
                except ValueError:
                    print("Invalid selection. Keeping current.")

            if not cfg["llm_binding_name"]:
                print("No LLM binding selected. Skipping parameters.")
                continue

            print(f"\nConfiguring '{cfg['llm_binding_name']}' Parameters:")
            cur_model = cfg.get("llm_binding_config", {}).get("model_name", "")
            cur_host = cfg.get("llm_binding_config", {}).get("host_address", "")
            cur_key = cfg.get("llm_binding_config", {}).get("api_key", "")

            # Fallbacks
            default_model = cur_model or "gpt-4o-mini"
            default_host = cur_host or ""
            if cfg["llm_binding_name"] == "ollama":
                default_model = cur_model or "llama3"
                default_host = cur_host or "http://localhost:11434"
            elif cfg["llm_binding_name"] == "open_router":
                default_model = cur_model or "meta-llama/llama-3-8b-instruct:free"
                default_host = cur_host or "https://openrouter.ai/api/v1"
            elif cfg["llm_binding_name"] == "claude":
                default_model = cur_model or "claude-3-5-sonnet-20240620"
            elif cfg["llm_binding_name"] == "gemini":
                default_model = cur_model or "gemini-1.5-flash"

            model_name = input(f"  Enter Model Name [{default_model}]: ").strip() or default_model
            new_llm_cfg = {"model_name": model_name}

            if cfg["llm_binding_name"] in ("ollama", "open_router", "vllm", "llama_cpp_server", "litellm"):
                host_prompt = f"  Enter Host Address [{default_host}]: " if default_host else "  Enter Host Address: "
                host_addr = input(host_prompt).strip() or default_host
                if host_addr:
                    new_llm_cfg["host_address"] = host_addr

            if cfg["llm_binding_name"] in ("openai", "open_router", "claude", "gemini", "litellm", "grok", "groq"):
                key_prompt = "  Enter API/Service Key (leave blank to keep current): " if cur_key else "  Enter API/Service Key: "
                api_key = input(key_prompt).strip()
                if api_key:
                    new_llm_cfg["api_key"] = api_key
                elif cur_key:
                    new_llm_cfg["api_key"] = cur_key

            cfg["llm_binding_config"] = new_llm_cfg

        elif choice == "2":
            # --- SECTION 2: TTI BINDING ---
            setup_tti = input(f"\nDo you want to enable Image Generation (TTI)? [Current: {'Yes' if cfg.get('tti_binding_name') else 'No'}] (y/N): ").strip().lower()
            if setup_tti == 'y':
                available_ttis = []
                if tti_bindings_dir.exists():
                    available_ttis = [d.name for d in tti_bindings_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
                if not available_ttis:
                    available_ttis = ["diffusers", "openai", "stability_ai", "gemini"]

                print("\nSelect TTI Binding Provider:")
                for idx, binding in enumerate(available_ttis):
                    print(f"  [{idx + 1}] {binding}")

                tti_choice = input(f"Enter selection number [Current: {cfg.get('tti_binding_name')}]: ").strip()
                if tti_choice:
                    try:
                        idx = int(tti_choice) - 1
                        if 0 <= idx < len(available_ttis):
                            cfg["tti_binding_name"] = available_ttis[idx]
                    except ValueError:
                        print("Invalid selection. Keeping current.")

                if not cfg["tti_binding_name"]:
                    print("No TTI binding selected. Skipping parameters.")
                    continue

                print(f"\nConfiguring '{cfg['tti_binding_name']}' Parameters:")
                cur_tmodel = cfg.get("tti_binding_config", {}).get("model_name", "")
                cur_tkey = cfg.get("tti_binding_config", {}).get("api_key", "")

                default_tmodel = cur_tmodel or ("stabilityai/sdxl-turbo" if cfg["tti_binding_name"] == "diffusers" else "dall-e-3")
                tti_model_name = input(f"  Enter TTI Model Name [{default_tmodel}]: ").strip() or default_tmodel

                new_tti_cfg = {"model_name": tti_model_name}
                if cfg["tti_binding_name"] in ("openai", "stability_ai", "gemini"):
                    key_prompt = "  Enter TTI API/Service Key (leave blank to keep current): " if cur_tkey else "  Enter TTI API/Service Key: "
                    tti_key = input(key_prompt).strip()
                    if tti_key:
                        new_tti_cfg["api_key"] = tti_key
                    elif cur_tkey:
                        new_tti_cfg["api_key"] = cur_tkey

                cfg["tti_binding_config"] = new_tti_cfg
            elif setup_tti == 'n':
                cfg["tti_binding_name"] = ""
                cfg["tti_binding_config"] = {}
=======
        if choice == "1":
            # --- SECTION 1: LLM BINDING ---
            available_llms = []
            if llm_bindings_dir.exists():
                available_llms = [d.name for d in llm_bindings_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
            if not available_llms:
                available_llms = ["ollama", "openai", "open_router", "claude", "gemini", "litellm", "vllm"]

            print("\nSelect LLM Binding Provider:")
            for idx, binding in enumerate(available_llms):
                print(f"  [{idx + 1}] {binding}")

            llm_choice = input(f"Enter selection number [Current: {cfg.get('llm_binding_name')}]: ").strip()
            if llm_choice:
                try:
                    idx = int(llm_choice) - 1
                    if 0 <= idx < len(available_llms):
                        cfg["llm_binding_name"] = available_llms[idx]
                except ValueError:
                    print("Invalid selection. Keeping current.")

            if not cfg["llm_binding_name"]:
                print("No LLM binding selected. Skipping parameters.")
                continue

            selected_llm = cfg["llm_binding_name"]

            # Dynamic parameter discovery for the selected binding
            import yaml
            lollms_client_dir = Path(lollms_client.__file__).parent
            binding_dir = lollms_client_dir / "llm_bindings" / selected_llm
            desc_file = binding_dir / "description.yaml"
            discovered_params = []
            if desc_file.exists():
                try:
                    with open(desc_file, "r", encoding="utf-8") as f:
                        desc_data = yaml.safe_load(f) or {}
                    for key_name in ("global_input_parameters", "input_parameters", "binding_parameters"):
                        if isinstance(desc_data.get(key_name), list):
                            discovered_params.extend(desc_data[key_name])
                except Exception:
                    pass

            # Fallback generic parameters if description.yaml was missing or failed to parse
            if not discovered_params:
                discovered_params = [
                    {"name": "host_address", "type": "str", "description": "The host address of the service.", "default": "http://localhost:11434" if selected_llm == "ollama" else ""},
                    {"name": "api_key", "type": "str", "description": "The API/Service Key for authentication.", "default": ""}
                ]

            # Load last known configuration for this specific selected binding
            saved_configs = cfg.get("llm_bindings_configs", {})
            saved_config = saved_configs.get(selected_llm, {})

            print(f"\nConfiguring '{selected_llm}' Parameters:")
            llm_config = {}

            for p in discovered_params:
                p_name = p.get("name")
                if p_name == "model_name":
                    continue  # We will select this after validation

                p_type = p.get("type", "str")
                # Look up priority: saved_config value -> default value -> empty string
                default_val = saved_config.get(p_name)
                if default_val is None:
                    default_val = p.get("default", "")

                label = p_name.replace("_", " ").title()
                desc = f" ({p.get('description')})" if p.get("description") else ""

                user_val = input(f"  Enter {label}{desc} [{default_val}]: ").strip()
                if not user_val:
                    val = default_val
                else:
                    try:
                        if p_type in ("int", "integer"):
                            val = int(user_val)
                        elif p_type in ("float", "double"):
                            val = float(user_val)
                        elif p_type in ("bool", "boolean"):
                            val = user_val.lower() in ("true", "1", "yes", "y")
                        else:
                            val = user_val
                    except ValueError:
                        val = user_val

                llm_config[p_name] = val

            # Connect to binding to query and list available models
            print(f"\n🔌 Connecting to '{selected_llm}' to retrieve available models...")
            selected_model = None
            try:
                import importlib
                module_path = f"lollms_client.llm_bindings.{selected_llm}"
                module = importlib.import_module(module_path)
                binding_class = getattr(module, getattr(module, "BindingName"))
                
                # Instantiate binding temporarily with entered config
                instance = binding_class(**llm_config)
                models = []
                if hasattr(instance, "list_models") and callable(instance.list_models):
                    models = instance.list_models()
                
                if models:
                    print("\nSelect an LLM Model from the list of available models:")
                    for m_idx, m in enumerate(models):
                        m_val = m.get("model_name") if isinstance(m, dict) else m
                        print(f"  [{m_idx + 1}] {m_val}")
                    
                    while True:
                        try:
                            m_choice = input(f"\nEnter selection number [1-{len(models)}]: ").strip()
                            if m_choice:
                                m_idx = int(m_choice) - 1
                                if 0 <= m_idx < len(models):
                                    selected_model = models[m_idx].get("model_name") if isinstance(models[m_idx], dict) else models[m_idx]
                                    break
                            else:
                                # Default to the saved model or first available model
                                current_saved_model = saved_config.get("model_name")
                                if current_saved_model and any((m.get("model_name") if isinstance(m, dict) else m) == current_saved_model for m in models):
                                    selected_model = current_saved_model
                                else:
                                    selected_model = models[0].get("model_name") if isinstance(models[0], dict) else models[0]
                                break
                        except ValueError:
                            pass
                        print("Invalid selection. Please try again.")
                else:
                    print("\n⚠️ No models returned by the binding. Please enter model name manually.")
            except Exception as e:
                print(f"\n❌ Connection failed: {e}")

            if not selected_model:
                current_saved_model = saved_config.get("model_name") or ""
                man_model = input(f"  Enter Model Name manually [{current_saved_model}]: ").strip()
                selected_model = man_model if man_model else current_saved_model

            llm_config["model_name"] = selected_model
            cfg["llm_binding_config"] = llm_config
            
            # Save right away to memory state
            cfg.setdefault("llm_bindings_configs", {})[selected_llm] = llm_config

        elif choice == "2":
            # --- SECTION 2: TTI BINDING ---
            setup_tti = input(f"\nDo you want to enable Image Generation (TTI)? [Current: {'Yes' if cfg.get('tti_binding_name') else 'No'}] (y/N): ").strip().lower()
            if setup_tti == 'y':
                available_ttis = []
                if tti_bindings_dir.exists():
                    available_ttis = [d.name for d in tti_bindings_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
                if not available_ttis:
                    available_ttis = ["diffusers", "openai", "stability_ai", "gemini"]

                print("\nSelect TTI Binding Provider:")
                for idx, binding in enumerate(available_ttis):
                    print(f"  [{idx + 1}] {binding}")

                tti_choice = input(f"Enter selection number [Current: {cfg.get('tti_binding_name')}]: ").strip()
                if tti_choice:
                    try:
                        idx = int(tti_choice) - 1
                        if 0 <= idx < len(available_ttis):
                            cfg["tti_binding_name"] = available_ttis[idx]
                    except ValueError:
                        print("Invalid selection. Keeping current.")

                if not cfg["tti_binding_name"]:
                    print("No TTI binding selected. Skipping parameters.")
                    continue

                selected_tti = cfg["tti_binding_name"]

                # Dynamic parameter discovery for the selected TTI binding
                import yaml
                lollms_client_dir = Path(lollms_client.__file__).parent
                binding_dir = lollms_client_dir / "tti_bindings" / selected_tti
                desc_file = binding_dir / "description.yaml"
                discovered_params = []
                if desc_file.exists():
                    try:
                        with open(desc_file, "r", encoding="utf-8") as f:
                            desc_data = yaml.safe_
