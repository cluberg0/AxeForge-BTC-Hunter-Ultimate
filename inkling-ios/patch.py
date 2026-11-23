#!/usr/bin/env python3
"""Patch upstream llama.cpp SwiftUI iOS example into InklingRunner v2."""
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path("llama-src").resolve()
app = root / "examples" / "llama.swiftui" / "llama.swiftui"
lib = root / "examples" / "llama.swiftui" / "llama.cpp.swift" / "LibLlama.swift"
files = Path(__file__).resolve().parent

def patch(path, changes):
    src = path.read_text(encoding="utf-8")
    for before, after in changes:
        occurrences = src.count(before)
        if occurrences != 1:
            raise RuntimeError(f"{path}: upstream source changed: {occurrences} occurrences of {before[:75]!r}")
        src = src.replace(before, after, 1)
    path.write_text(src, encoding="utf-8")
    print("Patched", path)

patch(lib, [
    ("var n_len: Int32 = 1024", "var n_len: Int32 = 384"),
    ("tokens_list = tokenize(text: text, add_bos: true)", """is_done = false
        tokens_list = tokenize(text: text, add_bos: true)
        // Prevent oversized attached document text from exceeding 512-token context.
        let maximumPromptTokens = max(64, Int(llama_n_ctx(context)) - Int(n_len) - 8)
        if tokens_list.count > maximumPromptTokens {
            tokens_list = Array(tokens_list.suffix(maximumPromptTokens))
        }"""),
    ("n_cur == n_len", "n_cur >= n_len"),
    ("let model = llama_model_load_from_file(path, model_params)", """model_params.n_gpu_layers = UserDefaults.standard.bool(forKey: "inkling_use_gpu") ? 99 : 0
        let model = llama_model_load_from_file(path, model_params)"""),
    ("ctx_params.n_ctx = 2048", """ctx_params.n_ctx = 512
        ctx_params.n_batch = 128
        ctx_params.n_ubatch = 32"""),
    ("""        llama_model_free(model)
        llama_free(context)""", """        llama_free(context)
        llama_model_free(model)"""),
])

state = app / "Models" / "LlamaState.swift"
patch(state, [
    ('@Published var messageLog = ""',
     '''@Published var messageLog = ""
    @Published var activeModelName = ""
    @Published var loadError = ""
    @Published var loading = false
    @Published var generatedText = ""
    @Published var isGenerating = false'''),
    ('    func loadModel(modelUrl: URL?) throws {',
     '''    func loadModelInBackground(modelUrl: URL) async {
        if loading { return }
        loading = true
        loadError = ""
        activeModelName = ""
        generatedText = ""
        messageLog += "Открываю модель: \\(modelUrl.lastPathComponent)\\n"
        // Free any previously loaded model before allocating a new large context.
        llamaContext = nil
        do {
            let path = modelUrl.path
            let newContext = try await Task.detached(priority: .userInitiated) {
                try LlamaContext.create_context(path: path)
            }.value
            llamaContext = newContext
            activeModelName = modelUrl.lastPathComponent
            messageLog += "Модель загружена: \\(modelUrl.lastPathComponent)\\n"
        } catch {
            loadError = "Не получилось загрузить GGUF: \\(error.localizedDescription). Проверьте архитектуру и память устройства."
            messageLog += loadError + "\\n"
        }
        loading = false
    }

    func loadModel(modelUrl: URL?) throws {'''),
    ('    func complete(text: String) async {\n        guard let llamaContext else {\n            return\n        }',
     '''    func complete(text: String) async {
        guard let llamaContext else {
            return
        }
        generatedText = ""
        isGenerating = true'''),
    ('                    self.messageLog += "\\(result)"',
     '''                    self.messageLog += "\\(result)"
                    self.generatedText += result'''),
    ('                self.messageLog += """',
     '''                self.isGenerating = false
                self.messageLog += """'''),
])

# Reuse already-registered Xcode source paths: no manual pbxproj editing necessary.
for source, destination in [
    ("ContentView.swift.txt", app / "UI" / "ContentView.swift"),
    ("HFModelLibrary.swift.txt", app / "UI" / "InputButton.swift"),
    ("X1Features.swift.txt", app / "UI" / "DownloadButton.swift"),
    ("X1Lidar.swift.txt", app / "UI" / "LoadCustomButton.swift"),
]:
    text = (files / source).read_text(encoding="utf-8")
    if not text.strip():
        raise RuntimeError(f"Empty template: {source}")
    destination.write_text(text, encoding="utf-8")
    print("Replaced", destination)

# Register UIKit lifecycle hook for background URLSession downloads.
launch = app / "llama_swiftuiApp.swift"
patch(launch, [
    ("struct llama_swiftuiApp: App {", """struct llama_swiftuiApp: App {
    @UIApplicationDelegateAdaptor(X1AppDelegate.self) private var appDelegate"""),
])

print("x1er_ai v3 source adaptation complete")
