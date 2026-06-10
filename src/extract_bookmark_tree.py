from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
import argparse
import sys


@dataclass
class FolderNode:
    name: str
    folders: list["FolderNode"] = field(default_factory=list)


class FirefoxBookmarkTreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = FolderNode("ROOT")
        self.folder_stack: list[FolderNode] = [self.root]
        self.pending_folder: FolderNode | None = None
        self.capture_h3 = False
        self.current_h3_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "h3":
            self.capture_h3 = True
            self.current_h3_text = []
        elif tag == "dl" and self.pending_folder is not None:
            self.folder_stack.append(self.pending_folder)
            self.pending_folder = None

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "h3":
            self.capture_h3 = False
            name = "".join(self.current_h3_text).strip()
            if name:
                node = FolderNode(name)
                self.folder_stack[-1].folders.append(node)
                self.pending_folder = node
            self.current_h3_text = []
        elif tag == "dl":
            if len(self.folder_stack) > 1:
                self.folder_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.capture_h3:
            self.current_h3_text.append(data)


def find_toolbar(root: FolderNode, target_name: str) -> FolderNode | None:
    for folder in root.folders:
        if folder.name == target_name:
            return folder
        found = find_toolbar(folder, target_name)
        if found is not None:
            return found
    return None


def render_tree(node: FolderNode) -> str:
    lines = [f"- {node.name}"]

    def walk(children: list[FolderNode], prefix: str) -> None:
        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            branch = "└─ " if is_last else "├─ "
            lines.append(f"{prefix}{branch}{child.name}")
            next_prefix = prefix + ("   " if is_last else "│  ")
            walk(child.folders, next_prefix)

    walk(node.folders, "")
    return "\n".join(lines)


def parse_bookmark_tree(bookmarks_path: Path, root_name: str) -> str:
    parser = FirefoxBookmarkTreeParser()
    parser.feed(bookmarks_path.read_text(encoding="utf-8"))

    toolbar = find_toolbar(parser.root, root_name)
    if toolbar is None:
        raise ValueError(f"未找到目标文件夹: {root_name}")

    return render_tree(toolbar)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从 Firefox 导出的 bookmarks.html 中提取文件夹 Tree。"
    )
    default_input = Path(__file__).resolve().parent.parent / "output" / "bookmarks.html"
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=default_input,
        help="Firefox 导出的 bookmarks.html 路径",
    )
    parser.add_argument(
        "-r",
        "--root-name",
        default="书签工具栏",
        help="要提取的根文件夹名称，默认是“书签工具栏”",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="可选：将结果写入文件，不传则打印到终端",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    try:
        tree_text = parse_bookmark_tree(args.input, args.root_name)
    except Exception as exc:  # pragma: no cover
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.write_text(tree_text + "\n", encoding="utf-8")
    else:
        print(tree_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())