#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ChatBox Markdown -> ChatGPT Conversation Import JSON

- 双击运行（.pyw）使用 Tk 窗口选择文件/文件夹。
- 命令行：
    python chatbox_md_to_chatgpt.pyw input.md
    python chatbox_md_to_chatgpt.pyw input.md output.json
"""

import json
import os
import sys
import time


# --------------------- 公共工具函数 ---------------------


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
        stripped = line.rstrip(" ")
        trailing = len(line) - len(stripped)
        if trailing > 0:
            line = stripped + ("\u00a0" * trailing)
        out_lines.append(line)
    return "\n".join(out_lines)


# --------------------- ChatBox Markdown 解析 ---------------------


def parse_code_block(lines, start_idx):
    """
    从 start_idx 行（角色行）之后开始，解析紧随其后的 ``` 代码块内容。
    返回 (文本, 下一个未处理的行索引)。
    如果没有找到合法代码块，则返回 ("", 下一个行索引)。
    """
    i = start_idx + 1
    n = len(lines)

    # 跳过空行
    while i < n and lines[i].strip() == "":
        i += 1

    # 期望是代码块起始行
    if i >= n or not lines[i].lstrip().startswith("```"):
        return "", i

    # 进入代码块
    i += 1
    block_lines = []
    while i < n and not lines[i].lstrip().startswith("```"):
        block_lines.append(lines[i])
        i += 1

    # 跳过结束 ``` 行
    if i < n and lines[i].lstrip().startswith("```"):
        i += 1

    return "\n".join(block_lines), i


def parse_chatbox_markdown(text: str):
    """
    解析 ChatBox 导出的 markdown：
    - 返回 file_title（# 行）
    - 以及 topics 列表，每个元素形如：
      {
        "heading": "1. 话题1",
        "messages": [
          {"role": "user" | "assistant" | "system", "text": "..."},
          ...
        ]
      }
    """
    lines = text.splitlines()
    n = len(lines)
    idx = 0

    # 解析总标题（# ...）
    file_title = "Untitled"
    if n > 0:
        first = lines[0].lstrip()
        if first.startswith("# "):
            title_candidate = first[2:].strip()
            file_title = title_candidate or "Untitled"
            idx = 1

    topics = []
    current_topic = None

    while idx < n:
        line = lines[idx]
        stripped = line.lstrip()

        # 元数据分隔线：之后全部忽略
        if line.strip().startswith("--------------------"):
            break

        # 话题标题：## N. XXX
        if stripped.startswith("## "):
            # 先收尾上一个话题（如果有内容）
            if current_topic is not None and current_topic["messages"]:
                topics.append(current_topic)

            heading_text = stripped[3:].strip()  # 去掉 "## "
            if not heading_text:
                heading_text = file_title

            current_topic = {
                "heading": heading_text,
                "messages": [],
            }
            idx += 1
            continue

        # 角色行：**user**: / **assistant**: / **system**:
        if stripped.startswith("**user**:"):
            msg_text, next_idx = parse_code_block(lines, idx)
            idx = next_idx
            if not is_all_whitespace(msg_text):
                if current_topic is None:
                    current_topic = {"heading": file_title, "messages": []}
                current_topic["messages"].append(
                    {"role": "user", "text": msg_text}
                )
            continue

        if stripped.startswith("**assistant**:"):
            msg_text, next_idx = parse_code_block(lines, idx)
            idx = next_idx
            if not is_all_whitespace(msg_text):
                if current_topic is None:
                    current_topic = {"heading": file_title, "messages": []}
                current_topic["messages"].append(
                    {"role": "assistant", "text": msg_text}
                )
            continue

        # if stripped.startswith("**system**:"):
        #     msg_text, next_idx = parse_code_block(lines, idx)
        #     idx = next_idx
        #     # system prompt 可以转为 system 消息，也可以忽略；这里按开发文档保留为 system 消息
        #     if not is_all_whitespace(msg_text):
        #         if current_topic is None:
        #             current_topic = {"heading": file_title, "messages": []}
        #         current_topic["messages"].append(
        #             {"role": "system", "text": msg_text}
        #         )
        #     continue

        # 其它行直接跳过
        idx += 1

    # 收尾最后一个话题
    if current_topic is not None and current_topic["messages"]:
        topics.append(current_topic)

    return file_title, topics


# --------------------- Conversation 对象构建 ---------------------


def build_conversation_object_from_topic(topic, conv_index: int, base_time: float):
    """
    把单个 ChatBox 话题转换成 ChatGPT Conversation 对象。
    topic:
      {
        "heading": "1. 话题1",
        "messages": [
          {"role": "user"|"assistant"|"system", "text": "..."},
          ...
        ]
      }
    """
    heading = topic.get("heading") or "Untitled"
    # 标题只取第一行，并在 30 字符后截断 + ...
    title = heading.splitlines()[0]
    if len(title) > 30:
        title = title[:30] + "..."

    messages = topic.get("messages", [])
    num_msgs = len(messages)

    create_time = base_time + conv_index
    update_time = create_time + num_msgs

    mapping = {}

    # 根节点
    root_children = ["msg-1"] if num_msgs > 0 else []
    mapping["client-created-root"] = {
        "id": "client-created-root",
        "message": None,
        "parent": None,
        "children": root_children,
    }

    # 消息节点
    for idx, msg in enumerate(messages, start=1):
        msg_id = f"msg-{idx}"
        parent_id = "client-created-root" if idx == 1 else f"msg-{idx - 1}"
        children = [f"msg-{idx + 1}"] if idx < num_msgs else []
        role = msg["role"]
        text = normalize_trailing_spaces(msg.get("text") or "")

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


def convert_chatbox_markdown_text(text: str):
    """
    将整个 ChatBox markdown 文本转换成 Conversation 对象列表。
    """
    file_title, topics = parse_chatbox_markdown(text)

    conversations = []
    base_time = time.time()
    conv_index = 0

    for topic in topics:
        if not topic.get("messages"):
            continue
        conv_index += 1
        conv_obj = build_conversation_object_from_topic(
            topic=topic,
            conv_index=conv_index,
            base_time=base_time,
        )
        conversations.append(conv_obj)

    return conversations


# --------------------- I/O 与运行模式 ---------------------


def convert_file(input_path: str, output_path: str):
    """
    读取一个 ChatBox 导出的 .md 文件，转换为 JSON 数组，写入 output_path。
    返回 (success: bool, error_message: str|None)
    """
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        return False, f"读取文件失败: {input_path} ({e})"

    try:
        conversations = convert_chatbox_markdown_text(text)
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

    # 问是否按文件夹批量
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

    # 文件模式：可以多选
    paths = filedialog.askopenfilenames(
        title="选择一个或多个 ChatBox Markdown (.md) 文件",
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

    # 多文件：不弹保存框，直接在各自目录旁生成 .json
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
        print("  python chatbox_md_to_chatgpt.pyw input.md [output.json]")
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
        # 命令行模式
        run_cli(sys.argv[1:])
    else:
        # GUI 模式
        run_gui()


if __name__ == "__main__":
    main()
