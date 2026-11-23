#!/usr/bin/env python3
"""Upgrade upstream llama.swiftui to multi-turn prompt support and correct token counting.

Run AFTER patch.py. Fail rather than silently applying an incompatible patch.
"""
from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path("llama-src").resolve()
lib=root/"examples"/"llama.swiftui"/"llama.cpp.swift"/"LibLlama.swift"
state=root/"examples"/"llama.swiftui"/"llama.swiftui"/"Models"/"LlamaState.swift"

def swap(source, old, new):
    count=source.count(old)
    if count != 1:
        raise RuntimeError(f"Upstream API mismatch (matches={count}): {old[:110]!r}")
    return source.replace(old,new,1)

def patch_engine():
    s=lib.read_text(encoding="utf-8")
    s=swap(s,"import llama\n",'''import llama

// App-level chat turns, not serialised by the runtime or sent to a server.
struct X1Turn: Sendable {
    let role: String
    let content: String
}

''')
    start=s.index("    func completion_init(text: String) {")
    end=s.index("    func completion_loop() -> String {",start)
    code='''    // Prepares a role-aware prompt. Prefer the GGUF's own chat template where the
    // llama.cpp built-in template API supports it. Fall back to explicit roles.
    private func formattedChat(_ turns: [X1Turn]) -> String {
        guard !turns.isEmpty else { return "" }

        if let tmpl = llama_model_chat_template(model, nil) {
            let roles = turns.map { strdup($0.role) }
            let contents = turns.map { strdup($0.content) }
            defer {
                for item in roles { if let item { free(item) } }
                for item in contents { if let item { free(item) } }
            }
            let msgs: [llama_chat_message] = zip(roles, contents).compactMap { role, content in
                guard let role, let content else { return nil }
                return llama_chat_message(role: role, content: content)
            }
            if msgs.count == turns.count {
                var buffer = [CChar](repeating: 0, count: 131_072)
                let written: Int32 = msgs.withUnsafeBufferPointer { input in
                    buffer.withUnsafeMutableBufferPointer { output in
                        llama_chat_apply_template(tmpl, input.baseAddress, input.count, true,
                                                  output.baseAddress, Int32(output.count))
                    }
                }
                if written > 0 && written < buffer.count {
                    let utf8 = buffer.prefix(Int(written)).map { UInt8(bitPattern: $0) }
                    if let prompt = String(bytes: utf8, encoding: .utf8) {
                        return prompt
                    }
                }
            }
        }
        // Some GGUFs use Jinja beyond the minimal built-in llama_chat_apply_template API.
        return turns.map { turn in
            "[\\\\(turn.role.uppercased())]\\\\n\\\\(turn.content)\\\\n"
        }.joined() + "[ASSISTANT]\\\\n"
    }

    func completion_init(turns: [X1Turn]) {
        let n_ctx = Int(llama_n_ctx(context))
        // Preserve requested space for the answer instead of truncating chat
        // template control tokens in the middle.
        let reserve = min(Int(n_len), max(64, n_ctx / 3))
        let promptBudget = max(32, n_ctx - reserve - 8)

        var selected = Array(turns.suffix(24))
        var prompt = formattedChat(selected)
        var tokens = tokenize(text: prompt, add_bos: false)

        while tokens.count > promptBudget && selected.count > 1 {
            // Drop the oldest completed turn. Keep newest user question intact.
            selected.removeFirst()
            prompt = formattedChat(selected)
            tokens = tokenize(text: prompt, add_bos: false)
        }
        if tokens.count > promptBudget, !selected.isEmpty {
            var last = selected[selected.count - 1]
            var text = last.content
            while tokens.count > promptBudget && text.count > 40 {
                text = String(text.suffix(max(40, Int(Double(text.count) * 0.76))))
                last = X1Turn(role: last.role, content: text)
                selected[selected.count - 1] = last
                prompt = formattedChat(selected)
                tokens = tokenize(text: prompt, add_bos: false)
            }
        }

        if tokens.count > promptBudget {
            // Guarantee a bounded batch. If a specialized template itself is
            // too verbose, retain the final tokens of the latest user message.
            let latest = selected.last?.content ?? ""
            var tail = String(latest.suffix(200))
            var fallback = "[USER]\\\\n\\\\(tail)\\\\n[ASSISTANT]\\\\n"
            var fitted = tokenize(text: fallback, add_bos: true)
            while fitted.count > promptBudget && tail.count > 20 {
                tail = String(tail.suffix(max(20, tail.count / 2)))
                fallback = "[USER]\\\\n\\\\(tail)\\\\n[ASSISTANT]\\\\n"
                fitted = tokenize(text: fallback, add_bos: true)
            }
            tokens = Array(fitted.suffix(promptBudget))
        }

        llama_sampler_reset(sampling)
        llama_memory_clear(llama_get_memory(context), true)
        temporary_invalid_cchars = []
        is_done = false
        n_decode = 0
        n_cur = 0
        tokens_list = tokens

        llama_batch_ext_clear(batch)
        for i in tokens.indices {
            let idx = llama_batch_add(batch, tokens[i], Int32(i), 0,
                                      i == tokens.count - 1)
            if idx < 0 {
                print("llama_batch_add failed at \\\\(i): \\\\(idx)")
                is_done = true
                return
            }
        }

        let status = llama_process(context, LLAMA_PROCESS_TYPE_DECODE, batch)
        if status != 0 {
            print("llama_process prefill failed: \\\\(status)")
            is_done = true
            return
        }
        n_cur = Int32(tokens.count)
    }

'''
    s=s[:start]+code+s[end:]
    s=swap(s,"n_cur >= n_len","n_decode >= n_len")
    lib.write_text(s,encoding="utf-8")
    print("Patched multi-turn chat template and context fitting",lib)

def patch_state():
    s=state.read_text(encoding="utf-8")
    s=swap(s,"func complete(text: String) async {","func complete(turns: [X1Turn]) async {")
    s=swap(s,"await llamaContext.completion_init(text: text)","await llamaContext.completion_init(turns: turns)")
    s=swap(s,'messageLog += "\\\\(text)"','messageLog += "\\\\(turns.last?.content ?? "")"')
    # Reset generation flag when the batch cannot be started, and don't loop on a
    # dead or never-prefilled context.
    s=swap(s,
'''        messageLog += "\\\\(turns.last?.content ?? "")"

        Task.detached {''',
'''        messageLog += "\\\\(turns.last?.content ?? "")"
        if await llamaContext.is_done {
            isGenerating = false
            loadError = "Не удалось подготовить контекст модели. Уменьши контекст или проверь GGUF."
            return
        }

        Task.detached {''')
    state.write_text(s,encoding="utf-8")
    print("Patched async state to consume role-aware messages",state)

patch_engine()
patch_state()
