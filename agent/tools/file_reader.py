"""文件读取工具：只允许读取白名单目录下的文本文件。"""

from pathlib import Path

READ_SCHEMA = {
    "name": "read_file",
    "description": "读取示例文档目录中的文本文件。只能使用文件名，如 notes.txt。",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "文件名，不含路径，如 notes.txt"},
        },
        "required": ["filename"],
    },
}

BASE_DIR = (Path(__file__).resolve().parent.parent / "sample_docs").resolve()
MAX_BYTES = 64 * 1024


def read_file(filename):
    if not isinstance(filename, str) or not filename.strip():
        return {"error": "invalid_input", "message": "文件名不能为空"}
    name = filename.strip()
    # 只允许纯文件名：拒绝路径分隔符与 ..
    if Path(name).name != name or name in (".", ".."):
        return {"error": "invalid_path", "message": "只能使用文件名，不能包含路径"}

    target = (BASE_DIR / name).resolve()
    if target.parent != BASE_DIR:
        return {"error": "invalid_path", "message": "文件不在允许的目录内"}
    if not target.is_file():
        return {"error": "file_not_found", "message": f"文件不存在：{name}"}
    if target.stat().st_size > MAX_BYTES:
        return {"error": "file_too_large", "message": f"文件超过 {MAX_BYTES // 1024}KB 限制"}
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"error": "not_text", "message": "文件不是 UTF-8 文本"}
    return {"filename": name, "content": content}