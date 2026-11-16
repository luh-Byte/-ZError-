# -*- coding: utf-8 -*-
"""
把 截图题库_焊接结构生产.json 导入 ZError 本地题库(SQLite: airesponses.db)。

写入口径与 import_to_zerror.py 完全一致:
    Options      选项串 "A. xxx  B. yyy"; 判断题为 NULL
    Answer       选项文字而非字母: 单选=正确选项原文; 多选=各选项文字用 ### 连接;
                 判断题="正确"/"错误"
    QuestionType single / multiple / judgement
    IsAi         0(导入题库, 非 AI 生成)
    FolderId/FolderName  独立文件夹"焊接结构生产"

用法:
    python import_screenshots.py            # 干跑, 只打印统计与清单
    python import_screenshots.py --apply    # 实际写入(自动先备份 db)
"""
import io, os, json, shutil, sqlite3, sys, datetime, collections

DB = r"C:\Users\liuyuhe\AppData\Local\ZError\airesponses.db"
SRC = r"D:\ZError\题库总库\截图题库_焊接结构生产.json"
FOLDER = "焊接结构生产"
TYPE_MAP = {"单选": "single", "多选": "multiple", "判断": "judgement"}
OPT_SEP = "  "


def build_options(opts):
    parts = []
    for idx, text in enumerate(opts):
        if not text:
            continue
        parts.append("%s. %s" % (chr(65 + idx), text))
    return OPT_SEP.join(parts) if parts else None


def build_answer(rec):
    qtype, opts, ans = rec["qtype"], rec["options"], (rec["answer"] or "").strip()
    if qtype == "判断":
        return ans if ans in ("正确", "错误") else None
    if not ans:
        return None
    texts = []
    for ch in ans:
        i = ord(ch) - 65
        if i < 0 or i >= len(opts) or not opts[i]:
            return None
        texts.append(opts[i])
    if not texts:
        return None
    return texts[0] if qtype == "单选" else "###".join(texts)


def load():
    data = json.loads(io.open(SRC, encoding="utf-8").read())
    rows, bad = [], collections.Counter()
    for rec in data["questions"]:
        qt = TYPE_MAP.get(rec["qtype"])
        if not qt:
            bad["题型未知"] += 1
            continue
        ans = build_answer(rec)
        if not ans:
            bad["答案无法还原"] += 1
            continue
        rows.append({
            "qid": rec["qid"],
            "src_no": rec.get("src_no"),
            "question": rec["question"],
            "options": build_options(rec["options"]) if qt in ("single", "multiple") else None,
            "answer": ans,
            "qtype": qt,
            "flags": rec.get("flags", []),
        })
    return rows, bad


def main():
    apply = "--apply" in sys.argv
    rows, bad = load()
    print("题库文件:", SRC)
    print("题目:", len(rows), " 异常:", dict(bad))
    print("\n按题型:", dict(collections.Counter(r["qtype"] for r in rows)))
    print("待复核:", [r["qid"] for r in rows if "答案待复核" in r["flags"]] or "无")
    print("\n清单:")
    for r in rows:
        tag = r["src_no"] if r["src_no"] else "-"
        print("  %s [%s/%s] %s" % (r["qid"], tag, r["qtype"], r["question"][:38]))
        print("      answer: %s" % r["answer"][:70])

    # 与库内同文件夹题干比对, 已存在的跳过
    conn = sqlite3.connect(DB)
    existing = {q for (q,) in conn.execute(
        "SELECT Question FROM AIResponses WHERE FolderName = ?", (FOLDER,))}
    kept, dup = [], 0
    for r in rows:
        if r["question"].strip() in existing:
            dup += 1
            continue
        kept.append(r)
    print("\n库内已有同题干跳过:", dup, "  实际待写入:", len(kept))

    if not apply:
        conn.close()
        print("\n(干跑) 加 --apply 才会写入:", DB)
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = "%s.bak-%s" % (DB, stamp)
    shutil.copy2(DB, backup)
    print("已备份数据库:", backup)

    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys=OFF")
    row = cur.execute("SELECT Id FROM Folders WHERE Name = ? AND ParentId = 0", (FOLDER,)).fetchone()
    if row:
        fid = row[0]
    else:
        cur.execute("INSERT INTO Folders (Name, ParentId, CreateTime) VALUES (?, 0, datetime('now'))", (FOLDER,))
        fid = cur.lastrowid
    before = cur.execute("SELECT COUNT(*) FROM AIResponses").fetchone()[0]
    for r in kept:
        cur.execute(
            "INSERT INTO AIResponses (Question, Answer, Options, QuestionType, IsAi, IsPendingCorrection, "
            "CreateTime, FolderId, FolderName) VALUES (?, ?, ?, ?, 0, 0, datetime('now'), ?, ?)",
            (r["question"], r["answer"], r["options"], r["qtype"], fid, FOLDER),
        )
    conn.commit()
    after = cur.execute("SELECT COUNT(*) FROM AIResponses").fetchone()[0]
    print("写入完成: 前 %d 条 → 后 %d 条, 本次插入 %d 条, 文件夹 Id=%d" % (before, after, after - before, fid))
    conn.close()


if __name__ == "__main__":
    main()
