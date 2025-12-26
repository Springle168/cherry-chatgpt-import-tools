# cherry-chatgpt-import-tools

将 **Cherry Studio** 和 **ChatBox** 导出的对话 Markdown 文件，转换为 Cherry Studio 可导入的 **ChatGPT 对话 JSON** 的 Python 脚本集合。

> 主要用途：把已有的单独一个（或多个）对话记录迁移到其它设备的 Cherry Studio 实例中，而不是通过官方备份与恢复功能导入全部数据。

---

## 功能概述

- 支持两种来源的导出文件：
  - Cherry Studio 导出的对话 Markdown（**不包含思考**的单个对话）
  - ChatBox 导出的对话 Markdown（多话题导出）
- 转换为符合 Cherry Studio「导入 ChatGPT 数据」功能的 JSON（conversation 数组）
- 支持：
  - 单文件转换
  - 多文件批量转换
  - 按文件夹批量转换
- Windows 下提供简单的图形界面（`.pyw`，双击运行）
- 处理了一些常见的导出问题：
  - Cherry Studio 的「清除上下文」拆分为多个 conversation
  - ChatBox 的多话题（`## 1. ...`、`## 2. ...`）拆分为多个 conversation
  - 尾部空格丢失问题（转成 `\u00a0` 避免导入后被吃掉）
  - 空消息、异常导出造成的结构问题（插入占位消息）

---

## 仓库结构

目前主要包含两个脚本：

- `cherry_md_to_chatgpt.pyw`
  将 **Cherry Studio 导出的 Markdown 对话文件** 转换为 ChatGPT conversation JSON。
- `chatbox_md_to_chatgpt.pyw`
  将 **ChatBox 导出的 Markdown 对话文件** 转换为 ChatGPT conversation JSON。

生成的 JSON 文件可以通过 Cherry Studio 的：

> 设置 → 数据设置 → 导入外部数据 → 导入 ChatGPT 数据

导入到其它设备 / 实例中。

---

## 适用场景

- 更换电脑 / 设备，希望把 Cherry Studio 里的少量对话历史迁移过去。
- 手上已经有 Cherry Studio / ChatBox 的 Markdown 导出，希望统一导入 Cherry Studio 里做归档。
- 只关心「文本内容」本身，代码块的语言标记、高亮等不是重点。

---

## 环境要求

- Python 3.8 及以上（建议 3.10+）
- Windows 用户：
  - 建议以 `.pyw` 后缀保存脚本，以避免双击运行时弹出多余的空白终端窗口。
  - 如果 `.pyw` 双击仍会打开空白终端，可以尝试删除脚本开头的 shebang 行（例如 `#!/usr/bin/env python`）。

---

## 使用方法

### 1. Windows 图形界面（推荐）

1. 安装 Python 3，并确保 `.pyw` 已关联到 `pythonw.exe`。
2. 将脚本保存为：
   - `cherry_md_to_chatgpt.pyw`
   - `chatbox_md_to_chatgpt.pyw`
3. 双击运行其中一个脚本：
   - 脚本会先询问：
     - 是否按「文件夹」批量转换，还是选择若干个文件。
   - **文件夹模式**：
     - 选择一个文件夹，脚本会自动转换该文件夹中所有 `.md` 文件；
     - 每个 `.md` 在同目录下生成同名 `.json`。
   - **多文件模式**：
     - 选择一个或多个 `.md` 文件；
     - 若只选 1 个文件：会弹出保存对话框，让你指定输出路径；
     - 若选多个文件：脚本在每个 `.md` 同目录下生成同名 `.json`，不会连续弹出保存对话框。

### 2. 命令行方式

```bash
# Cherry Studio 导出文件转换
python cherry_md_to_chatgpt.pyw input.md
python cherry_md_to_chatgpt.pyw input.md output.json

# ChatBox 导出文件转换
python chatbox_md_to_chatgpt.pyw input.md
python chatbox_md_to_chatgpt.pyw input.md output.json
```

不指定 `output.json` 时，会默认在同目录下生成 `input.json`。

---

## 详细行为说明

### 1. Cherry Studio 转换脚本：`cherry_md_to_chatgpt.pyw`

#### 1.1 输入格式假设

- 文件开头只有一个 `# 标题`（总标题），比如：

  ```markdown
  # Conversation Title
  ```
- 后面是重复出现的两种结构：

  ```markdown
  ## 🧑‍💻 User

  （用户消息内容，可能是多行）

  ---
  ## 🤖 Assistant
  （助手消息内容，可能是多行）
  ```
- Cherry Studio 目前导出时会在消息块之间插入 `---` 分隔线：

  - 脚本只会在「消息块的最后一行是单独的 `---`」时将其删除；
  - 正文中你自己写的 `---` 会保留。

#### 1.2 清除上下文（多 conversation 拆分）

- 若某个 `## 🧑‍💻 User` 块 **仅包含空白字符**（空格 / 换行等），视为 Cherry Studio 的「清除上下文」：
  - 不生成用户消息；
  - 截断当前对话段，后续内容作为一个新的 conversation。
- 文件末尾如果还有残留的对话段，会生成最后一个 conversation。

#### 1.3 空消息与占位

- 完全为空 / 仅空白的 `assistant` 块不会生成消息。
- 过滤掉空块之后，如果出现：

  - `user` 连着 `user`，或
  - `assistant` 连着 `assistant`

  脚本会在中间自动插入一条占位消息：

  ```text
  [空消息占位]
  ```

  以保证对话结构在导入后尽量规整。（实际上不加占位消息也能正常导入）

#### 1.4 Conversation 标题 & 时间戳

- 每个拆出来的 conversation 标题：
  - 使用该段对话中**第一条非占位消息**的**首行内容**；
  - 若长度超过 30 个字符，会截断为前 30 个字符并在末尾加上 `...`；
  - 若整段没有任何消息，则退回使用文件开头的 `#` 标题。
- 时间戳策略：
  - 以脚本运行时 `time.time()` 为基准；
  - 第 `i` 个 conversation：
    - `create_time = base + i`
    - `update_time = create_time + 消息数量`

#### 1.5 文本与空白处理

- 不会对消息内容做 `.strip()`，不会移除首尾空白；
- 只在判断「清除上下文」时用临时变量检查是否全空白；
- 写入 JSON 前，针对每一行：
  - 结尾连续的普通空格 `' '` 会被替换为对应数量的 `\u00a0`（不间断空格）；
  - 行内中间的空格保持不变；
- 这样可以避免 Cherry Studio 导入时自动吃掉尾部空格，保持内容更接近原始导出。

---

### 2. ChatBox 转换脚本：`chatbox_md_to_chatgpt.pyw`

#### 2.1 输入格式假设

- 文件开头只有一个 `# 标题`（总标题），比如：

  ```markdown
  # Untitled
  ```
- 后面是多个话题（topics），每个话题形如：

  ````markdown
  ## 1. 话题1

  **user**: 

  ```
  用户输入内容（在代码块中）
  ```

  **assistant**: 

  ```
  助手回复内容（在代码块中）
  ```
  ````
- `**user**:` / `**assistant**:` 后面紧跟一个 ``` 代码块，脚本会提取代码块内部的内容作为消息内容。
- 话题之间用二级标题区分：

  ```markdown
  ## 1. 话题1
  ...
  ## 2. 话题2
  ...
  ```
- 脚本只在**代码块外**识别 `## N. XXX`，不会误把消息正文中的 `## 5. Untitled` 当成新的话题标题。
- 文件末尾通常会有类似：

  ```markdown
  --------------------

  <a href="https://chatboxai.app" ...>...</a>
  ```

  从 `--------------------` 这一行开始的内容会全部忽略。

#### 2.2 System Prompt 处理

- ChatBox 导出中可能出现：

  ````markdown
  **system**:

  ```
  You are a helpful assistant.
  ```
  ````
- 实测在 Cherry Studio 中导入 system 消息会以「看起来像用户发出的消息，但不会真实发送」的形式出现，体验不佳。
- 因此当前脚本**直接忽略所有 `system` 消息**，不将其导入。

#### 2.3 空话题与干扰项

- 某些话题（例如 `## 3. Untitled`）可能完全没有任何有效消息，这可能是 ChatBox 导出时的 bug。
  - 脚本会自动跳过这些空话题，不生成对应的 conversation。
- 某些用户消息中可能出现类似 `## 5. Untitled` 的文本（例如你刻意输入的干扰项），因为被包在代码块中：
  - 脚本不会把它识别为新话题标题；
  - 这部分会被完整保留为用户消息的一部分。

#### 2.4 Conversation 标题 & 时间戳

- 每个话题转换成一个 conversation。
- conversation 标题：
  - 使用该话题的二级标题文本，例如 `1. 话题1`、`2. 话题2`；
  - 只取标题首行，长度超过 30 字符会截断并加 `...`。
- 时间戳策略与 Cherry Studio 脚本一致：
  - 以脚本运行时刻为基准，每个 conversation 的 `create_time`、`update_time` 递增。

#### 2.5 文本与空白处理

- 代码块内部的正文会原样取出；
- 同样会对每一行的尾部空格进行 `\u00a0` 替换，以避免导入时丢失尾部空白。

---

## 已知局限与不可抗力

### 1. Cherry Studio 导出导致的缩进丢失

目前 Cherry Studio 的对话导出存在一个已知问题：

- 导出的 Markdown 会 **错误地压缩行首空格**；
- 这会破坏 Markdown 中多级列表的缩进语义；
- 实际效果是：多级列表在导出后会被“拍平”为一级列表。

这属于 **Cherry Studio 导出功能本身的 bug**。
本脚本读取到的就是已经被破坏的文本，无法准确还原原始的缩进结构，因此：

- 本脚本只保证对话文本能被导入；
- 无法修复被破坏的列表缩进及其语义结构。

若你非常依赖多级列表/缩进展示，建议等待 Cherry Studio 修复导出的行为。

---

### 2. ChatBox 导出导致的代码块信息丢失

ChatBox 的导出（尤其是富文本/代码块部分）也存在一些问题：

- 某些情况下，导出的 Markdown 会 **丢失代码块的 &#96;&#96;&#96; 边界和语言标记**（例如```python）；
- 导出的结果看起来像“纯代码字符串”，而不是标准 Markdown 代码块。

本脚本：

- 只能基于 **外层仍然存在的 ``` 代码块** 来解析；
- 对已经被导出成「纯文本」的代码内容，脚本无法知道其原本的边界和语言种类，也就无法自动修复。

从设计角度，本项目的主要目标是：

> 方便迁移对话文本内容，而不是完美还原所有复杂的代码块结构或语法高亮。

因此，在代码块被导出破坏的情况下，本脚本只会 **原样导入文本内容**，不尝试进行算法级的智能修复。

---

## 常见问题（FAQ）

### Q1: 为什么在 Cherry Studio 中看不到 system prompt？

本项目的 ChatBox 转换脚本中刻意 **忽略了所有 `system` 消息**，原因是：

- 导入后 system prompt 会以“像用户消息一样”的形式显示在界面中；
- 但这些内容并不会在后续对话中真实发送，容易造成混淆。

如果你确实需要导入 system prompt，可以自行修改脚本，把相关忽略逻辑还原成 `role: "system"` 的消息节点。

---

### Q2: 为什么双击脚本时会弹出一个空白的命令行窗口？

建议：

- 将脚本文件命名为 `.pyw` 后缀，例如 `cherry_md_to_chatgpt.pyw`；
- 并确保 `.pyw` 与 `pythonw.exe` 相关联。

如果依然会出现空白终端，可以尝试：

- 删除脚本开头的 shebang，如：

  ```python
  #!/usr/bin/env python
  # -*- coding: utf-8 -*-
  ```

在本仓库中，这两行已经可以不必保留。

---

## 贡献与反馈

欢迎：

- 提交 Issue 反馈导入失败、解析异常等情况；
- 提交 Pull Request 优化解析逻辑，或支持更多导出来源。

由于上游应用的导出格式可能变动，本项目会尽量保持兼容，但不能保证对所有历史版本都完全适配。

---

## 许可协议（License）

本项目采用 [MIT License](LICENSE)。

你可以自由地使用、修改和分发本项目代码，但在再分发时需要保留原始的许可声明。

---

## 关于 AI 协助的说明

本项目部分代码和实现细节是在作者的控制下，借助大型语言模型生成或优化的。
作者对脚本进行了实际测试和调整，对最终版本负责。

你可以将本项目视为“人机协作”的成果，而不是未经审阅的自动生成代码。
