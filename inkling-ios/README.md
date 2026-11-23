# InklingRunner iOS IPA (experimental)
This is an isolated development branch; firmware on `main` is untouched.

A SwiftUI local-GGUF runner based on the official `ggml-org/llama.cpp` iOS example, rebuilt using current llama.cpp with `inkling2_loop` support.

Features: local GGUF import from Files, Metal enable/disable toggle, CPU-first setting, low memory context (512 tokens), offline inference. The 8.67 GB model is NOT bundled; use your downloaded `Inkling-2-Mini-Uncensored-AD-IQ2_M.gguf`.

Build: GitHub Actions -> **Build InklingRunner unsigned IPA** -> successful run -> artifact **InklingRunner-iOS-unsigned-IPA** -> unzip -> sideload the IPA with SideStore.

Important: unsigned IPA must be re-signed by SideStore. Even if compilation succeeds, no one has verified this model fitting the iPhone's per-app iOS RAM limit. This is a best-effort experimental app, not a guaranteed fix.
