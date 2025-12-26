#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cherry Studio Markdown -> ChatGPT Conversation Import JSON

- 双击运行（.pyw）使用 Tk 窗口选择文件/文件夹。
- 命令行：
    python cherry_md_to_chatgpt.pyw input.md
    python cherry_md_to_chatgpt.pyw input.md output.json
"""

import json
import os
import sys
import time


# --------------------- 核心解析与转换逻辑 ---------------------


def is_all_whitespace(text: str) -> bool:
    """Return True if text contains only whitespace (or is empty)."""
    if text is None:
        return True
    return not any(not ch.isspace() for ch in text)


def normalize_trailing_spaces(text: str) -> str:
    """
    Replace trailing ASCII spaces in each line with NBSP (\u00a0)
    to avoid being stripped after import.
    """
    if not text:
        return text
    lines = text.split("\n")
    out_lines = []
    for line in lines:
        # Count trailing spaces
        stripped = line.rstrip(" ")
        trailing = len(line) - len(stripped)
        if trailing > 0:
            line = stripped + ("\u00a0" * trailing)
        out_lines.append(line)
    return "\n".join(out_lines)


def trim_single_newlines(text: str) -> str:
    """Remove single newline characters at the beginning and end of the text."""
    if not text:
        return text
    if text.startswith("\n"):
        text = text[1:]
    if text.endswith("\n"):
        text = text[:-1]
    return text


def parse_markdown(text: str):
    """
    Parse Cherry Studio exported markdown into:
    - file_title (from first '# ' line, or 'Untitled')
    - raw_blocks: list of (role, text) where role in {'user', 'assistant'}
    """
    lines = text.splitlines()
    file_title = "Untitled"
    start_idx = 0

    if lines:
        first = lines[0].lstrip()
        if first.startswith("# "):
            title_candidate = first[2:].strip()
            file_title = title_candidate or "Untitled"
            start_idx = 1

    raw_blocks = []
    current_role = None
    current_lines = []

    def flush_current():
        nonlocal current_role, current_lines
        if current_role is None:
            return
        # Drop a trailing '---' line if present
        if current_lines and current_lines[-1].strip() == "---":
            current_lines.pop()
        block_text = "\n".join(current_lines)
        raw_blocks.append((current_role, block_text))
        current_role = None
        current_lines = []

    for line in lines[start_idx:]:
        stripped = line.strip()
        if stripped == "## 🧑‍💻 User":
            flush_current()
            current_role = "user"
            current_lines = []
        elif stripped == "## 🤖 Assistant":
            flush_current()
            current_role = "assistant"
            current_lines = []
        else:
            if current_role is not None:
                current_lines.append(line)
            # lines before first '## 🧑‍💻 User' / '## 🤖 Assistant' are ignored

    flush_current()
    return file_title, raw_blocks


def split_into_conversations(raw_blocks):
    """
    Split raw_blocks into segments by 'clear context' markers:
    - A user block whose text is all whitespace is treated as "clear context".
    """
    conversations = []
    current = []

    for role, text in raw_blocks:
        if role == "user" and is_all_whitespace(text):
            # Clear context: cut current conversation (if any)
            if current:
                conversations.append(current)
                current = []
            continue
        current.append((role, text))

    if current:
        conversations.append(current)

    return conversations


def normalize_blocks_for_conversation(blocks):
    """
    For a single conversation (list of (role, text)):
    - Remove blocks that are all whitespace.
    - Insert placeholder blocks '[空消息占位]' when two consecutive roles are equal.
    Returns a list of dicts: {'role': ..., 'text': ..., 'placeholder': bool}
    """
    filtered = [(r, t) for (r, t) in blocks if not is_all_whitespace(t)]
    if not filtered:
        return []

    result = []
    prev_role = None
    for role, text in filtered:
        if prev_role == role:
            # Insert placeholder from opposite role
            placeholder_role = "assistant" if role == "user" else "user"
            result.append(
                {
                    "role": placeholder_role,
                    "text": "[空消息占位]",
                    "placeholder": True,
                }
            )
        result.append(
            {
                "role": role,
                "text": text,
                "placeholder": False,
            }
        )
        prev_role = role

    return result


def build_conversation_object(blocks, conv_index: int, file_title: str, base_time: float):
    """
    Given normalized blocks (with placeholders), build a Conversation JSON object.
    """
    # Determine title: first non-placeholder message's first line
    title = None
    for b in blocks:
        if not b.get("placeholder"):
            text = b.get("text") or ""
            if text:
                first_line = text.splitlines()[0]
                title = first_line
                break

    if not title:
        title = file_title or "Untitled"

    # Truncate at newline already handled; now enforce 30-char limit
    if len(title) > 30:
        title = title[:30] + "..."

    create_time = base_time + conv_index
    update_time = create_time + len(blocks)

    mapping = {}
    num_msgs = len(blocks)

    # Root node
    root_children = ["msg-1"] if num_msgs > 0 else []
    mapping["client-created-root"] = {
        "id": "client-created-root",
        "message": None,
        "parent": None,
        "children": root_children,
    }

    # Message nodes
    for idx, b in enumerate(blocks, start=1):
        msg_id = f"msg-{idx}"
        parent_id = "client-created-root" if idx == 1 else f"msg-{idx - 1}"
        children = [f"msg-{idx + 1}"] if idx < num_msgs else []
        role = b["role"]
        text = normalize_trailing_spaces(b["text"] or "")
        text = trim_single_newlines(text)

        mapping[msg_id] = {
            "id": msg_id,
            "message": {
                "id": msg_id,
                "author": {"role": role},
                "content": {
                    "content_type": "text",
                    "parts": [text],
                },
            },
            "parent": parent_id,
            "children": children,
        }

    current_node = f"msg-{num_msgs}" if num_msgs > 0 else None
    conv_id = f"conv-{conv_index}"

    conversation = {
        "title": title,
        "create_time": create_time,
        "update_time": update_time,
        "mapping": mapping,
        "current_node": current_node,
        "conversation_id": conv_id,
        "id": conv_id,
    }

    return conversation


def convert_markdown_text(text: str):
    """
    Convert whole markdown text into a list of Conversation objects.
    """
    file_title, raw_blocks = parse_markdown(text)
    segments = split_into_conversations(raw_blocks)
    conversations = []

    base_time = time.time()
    conv_index = 0

    for seg in segments:
        blocks = normalize_blocks_for_conversation(seg)
        if not blocks:
            continue
        conv_index += 1
        conv_obj = build_conversation_object(
            blocks=blocks,
            conv_index=conv_index,
            file_title=file_title,
            base_time=base_time,
        )
        conversations.append(conv_obj)

    return conversations


# --------------------- I/O 与运行模式 ---------------------


def convert_file(input_path: str, output_path: str):
    """
    Read a .md file, convert, and write JSON array to output_path.
    Return (success: bool, error_message: str|None)
    """
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        return False, f"读取文件失败: {input_path} ({e})"

    try:
        conversations = convert_markdown_text(text)
    except Exception as e:
        return False, f"解析/转换失败: {input_path} ({e})"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(conversations, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return False, f"写入 JSON 失败: {output_path} ({e})"

    return True, None


# --------------------- GUI 模式（Tkinter） ---------------------


def setup_windows_dpi_awareness():
    """Try to enable high-DPI awareness on Windows to avoid blurry Tk windows."""
    try:
        import ctypes
        try:
            # Windows 8.1+
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                # Older Windows
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    except Exception:
        pass


def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox

    setup_windows_dpi_awareness()

    root = tk.Tk()
    root.withdraw()

    # Ask whether to use folder mode
    use_folder = messagebox.askyesno(
        "选择模式",
        "是否按文件夹批量转换？\n\n"
        "是：选择一个文件夹，转换其中所有 .md 文件\n"
        "否：选择一个或多个 .md 文件",
    )

    if use_folder:
        folder = filedialog.askdirectory(title="选择包含 Markdown 文件的文件夹")
        if not folder:
            messagebox.showinfo("取消", "未选择文件夹，已取消。")
            return

        md_files = [
            os.path.join(folder, name)
            for name in os.listdir(folder)
            if name.lower().endswith(".md")
        ]
        if not md_files:
            messagebox.showinfo("提示", "该文件夹中没有 .md 文件。")
            return

        successes = 0
        failures = []
        for path in sorted(md_files):
            out_path = os.path.splitext(path)[0] + ".json"
            ok, err = convert_file(path, out_path)
            if ok:
                successes += 1
            else:
                failures.append(err)

        msg = f"已完成转换：{successes} 个文件。"
        if failures:
            msg += "\n\n以下文件转换失败：\n" + "\n".join(failures)
        messagebox.showinfo("完成", msg)
        return

    # File(s) mode
    paths = filedialog.askopenfilenames(
        title="选择一个或多个 Markdown (.md) 文件",
        filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
    )
    if not paths:
        messagebox.showinfo("取消", "未选择文件，已取消。")
        return

    paths = list(paths)
    if len(paths) == 1:
        in_path = paths[0]
        base_dir = os.path.dirname(in_path)
        base_name = os.path.splitext(os.path.basename(in_path))[0]
        default_out = os.path.join(base_dir, base_name + ".json")

        out_path = filedialog.asksaveasfilename(
            title="保存为 JSON 文件",
            initialdir=base_dir,
            initialfile=base_name + ".json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not out_path:
            messagebox.showinfo("取消", "未选择保存位置，已取消。")
            return

        ok, err = convert_file(in_path, out_path)
        if ok:
            messagebox.showinfo("完成", f"转换成功：\n{in_path}\n→\n{out_path}")
        else:
            messagebox.showerror("错误", err)
        return

    # Multiple files, no save dialogs; output beside each input
    successes = 0
    failures = []
    for path in paths:
        out_path = os.path.splitext(path)[0] + ".json"
        ok, err = convert_file(path, out_path)
        if ok:
            successes += 1
        else:
            failures.append(err)

    msg = f"已完成转换：{successes} 个文件。"
    if failures:
        msg += "\n\n以下文件转换失败：\n" + "\n".join(failures)
    messagebox.showinfo("完成", msg)


# --------------------- 命令行入口 ---------------------


def run_cli(args):
    if not args:
        print("用法:")
        print("  python cherry_md_to_chatgpt.pyw input.md [output.json]")
        return

    input_path = args[0]
    if not os.path.isfile(input_path):
        print(f"输入文件不存在: {input_path}", file=sys.stderr)
        return

    if len(args) >= 2:
        output_path = args[1]
    else:
        base = os.path.splitext(input_path)[0]
        output_path = base + ".json"

    ok, err = convert_file(input_path, output_path)
    if ok:
        print(f"转换成功: {input_path} -> {output_path}")
    else:
        print(err, file=sys.stderr)


def main():
    if len(sys.argv) > 1:
        # Command-line mode
        run_cli(sys.argv[1:])
    else:
        # GUI mode
        run_gui()


if __name__ == "__main__":
    main()
