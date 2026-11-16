# -*- coding: utf-8 -*-
"""
把 tiku_all.json 导入一台新电脑上的 ZError 本地题库。

用法（在本文件所在目录）：
    python 导入ZError.py            # 干跑，只看统计
    python 导入ZError.py --apply    # 实际写入，自动先备份 db

可选：
    --db "D:\\path\\airesponses.db"   # 指定数据库路径（默认 %LOCALAPPDATA%\\ZError\\airesponses.db）
    --src "D:\\path\\tiku_all.json"   # 指定题库文件（默认与本脚本同目录）
"""
import io, os, sys, json, shutil, sqlite3, argparse, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ZError", "airesponses.db")

DDL_AI = """CREATE TABLE IF NOT EXISTS AIResponses (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Question TEXT NOT NULL,
    Options TEXT,
    QuestionType TEXT,
    Answer TEXT NOT NULL,
    CreateTime DATETIME DEFAULT CURRENT_TIMESTAMP,
    FolderId INTEGER DEFAULT 0,
    FolderName TEXT DEFAULT '默认文件夹',
    IsAi BOOLEAN DEFAULT 1,
    IsPendingCorrection BOOLEAN DEFAULT 0)"""
DDL_FOLDER = """CREATE TABLE IF NOT EXISTS Folders (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    ParentId INTEGER DEFAULT 0,
    CreateTime DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ParentId) REFERENCES Folders(Id))"""

KNOWN_TYPES = {"single", "multiple", "judgement", "completion"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--src", default=os.path.join(HERE, "tiku_all.json"))
    a = ap.parse_args()

    if not os.path.exists(a.src):
        sys.exit("找不到题库文件: %s" % a.src)
    if not os.path.exists(a.db):
        sys.exit("找不到 ZError 数据库: %s\n请先安装 ZError 并启动一次（让它自己建库），或用 --db 指定路径。" % a.db)

    recs = json.loads(io.open(a.src, encoding="utf-8").read())
    bad = [r for r in recs if r["qtype"] not in KNOWN_TYPES or not r["answer"]]
    good = [r for r in recs if r not in bad]
    by_folder = collections.Counter(r["folder"] for r in good)
    by_type = collections.Counter(r["qtype"] for r in good)

    print("题库文件:", a.src)
    print("目标数据库:", a.db)
    print("题目:", len(good), " 跳过(题型/答案异常):", len(bad))
    print("文件夹:", len(by_folder), " 题型:", dict(by_type))

    conn = sqlite3.connect(a.db)
    conn.execute(DDL_AI)
    conn.execute(DDL_FOLDER)
    existing = {(f, q) for f, q in conn.execute("SELECT FolderName, Question FROM AIResponses")}
    kept, dup = [], 0
    for r in good:
        key = (r["folder"], r["question"])
        if key in existing:
            dup += 1
            continue
        kept.append(r)
    print("本机已存在同题干跳过:", dup, " 实际待写入:", len(kept))

    if not a.apply:
        conn.close()
        print("\n(干跑) 确认无误后加 --apply 才会写入。")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = "%s.bak-%s" % (a.db, stamp)
    shutil.copy2(a.db, backup)
    print("已备份数据库:", backup)

    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys=OFF")
    folders = {}
    for name in by_folder:
        row = cur.execute("SELECT Id FROM Folders WHERE Name = ? AND ParentId = 0", (name,)).fetchone()
        if row:
            folders[name] = row[0]
        else:
            cur.execute("INSERT INTO Folders (Name, ParentId, CreateTime) VALUES (?, 0, datetime('now'))", (name,))
            folders[name] = cur.lastrowid

    before = cur.execute("SELECT COUNT(*) FROM AIResponses").fetchone()[0]
    for r in kept:
        cur.execute(
            "INSERT INTO AIResponses (Question, Answer, Options, QuestionType, IsAi, IsPendingCorrection, "
            "CreateTime, FolderId, FolderName) VALUES (?, ?, ?, ?, 0, 0, datetime('now'), ?, ?)",
            (r["question"], r["answer"], r["options"], r["qtype"], folders[r["folder"]], r["folder"]))
    conn.commit()
    after = cur.execute("SELECT COUNT(*) FROM AIResponses").fetchone()[0]
    print("写入完成: 前 %d 条 → 后 %d 条，本次插入 %d 条" % (before, after, after - before))
    print("\n各文件夹题量:")
    for name, n in cur.execute("SELECT FolderName, COUNT(*) FROM AIResponses GROUP BY FolderName ORDER BY COUNT(*) DESC"):
        print("  %-14s %5d" % (name, n))
    conn.close()


if __name__ == "__main__":
    main()
