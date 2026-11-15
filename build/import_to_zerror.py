# -*- coding: utf-8 -*-
"""
把 tiku_master.json 导入 ZError 的本地题库(SQLite: airesponses.db)。

ZError 的题库就是 AIResponses 表, 实测写入格式(来自 zerror.exe 内嵌 SQL 与提示词):
    Question     题干
    Options      选项串, 形如 "A. xxx  B. yyy"; 判断题/填空题为 NULL
    Answer       答案正文(不是字母): 单选=正确选项文字; 多选=各选项文字用 ### 连接;
                 判断题="正确"/"错误"; 填空=答案正文(多空用 ### 连接)
    QuestionType single / multiple / judgement / completion
    IsAi         0=非 AI 生成(导入的题库)
    FolderId / FolderName  按课程分文件夹

用法:
    python import_to_zerror.py            # 干跑, 只打印统计与样例
    python import_to_zerror.py --apply    # 实际写入(先自行备份 db)
"""
import io, os, json, sqlite3, sys, collections

DB = r"C:\Users\liuyuhe\AppData\Local\ZError\airesponses.db"
MASTER = r"D:\ZError\题库总库\tiku_master.json"

# 这些标记的题缺答案/缺选项, 导入后只会拖累匹配, 一律跳过
SKIP_FLAGS = {"缺答案", "源标注无答案", "选项缺失,答案索引无法还原", "无选项"}
TYPE_MAP = {"单选": "single", "多选": "multiple", "判断": "judgement", "填空": "completion"}
OPT_SEP = "  "


def build_options(opts):
    """选项串: 'A. xxx  B. yyy'"""
    parts = []
    for idx, text in enumerate(opts):
        if not text:
            continue
        parts.append("%s. %s" % (chr(65 + idx), text))
    return OPT_SEP.join(parts) if parts else None


def build_answer(rec):
    """把字母答案换成选项文字, 与 ZError 的答案口径一致"""
    qtype, opts = rec["qtype"], rec["options"]
    ans = rec["answer"]
    if qtype == "判断":
        return ans if ans in ("正确", "错误") else None
    if qtype == "填空":
        text = (ans or "").strip()
        if not text:
            return None
        return text.replace(" / ", "###")
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


def main():
    apply = "--apply" in sys.argv
    recs = json.loads(io.open(MASTER, encoding="utf-8").read())

    rows, skipped = [], collections.Counter()
    for r in recs:
        if SKIP_FLAGS & set(r["flags"]):
            skipped["缺答案/缺选项"] += 1
            continue
        ans = build_answer(r)
        if not ans:
            skipped["答案无法转成选项文字"] += 1
            continue
        qt = TYPE_MAP.get(r["qtype"])
        if not qt:
            skipped["题型未知"] += 1
            continue
        rows.append({
            "course": r["course"],
            "question": r["question"],
            "options": build_options(r["options"]) if r["qtype"] in ("单选", "多选") else None,
            "answer": ans,
            "qtype": qt,
        })

    # 同一课程内题干重复的, 只留第一条(避免一次查询命中多条)
    seen, dedup = set(), 0
    kept = []
    for r in rows:
        key = (r["course"], r["question"])
        if key in seen:
            dedup += 1
            continue
        seen.add(key)
        kept.append(r)

    by_course = collections.Counter(r["course"] for r in kept)
    print("待导入:", len(kept), "  跳过:", dict(skipped), "  课内重复去重:", dedup)
    print("\n按课程:")
    for c, n in by_course.most_common():
        print("  %-16s %5d" % (c, n))
    print("\n样例:")
    for r in kept[:3] + kept[-3:]:
        print("  [%s/%s] %s" % (r["course"], r["qtype"], r["question"][:40]))
        print("     options:", (r["options"] or "")[:90])
        print("     answer :", r["answer"][:60])

    if not apply:
        print("\n(干跑) 加 --apply 才会写入:", DB)
        return

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys=OFF")
    cur = conn.cursor()

    # 每个课程一个文件夹(已存在则复用)
    folders = {}
    for c in by_course:
        row = cur.execute("SELECT Id FROM Folders WHERE Name = ? AND ParentId = 0", (c,)).fetchone()
        if row:
            folders[c] = row[0]
        else:
            cur.execute("INSERT INTO Folders (Name, ParentId, CreateTime) VALUES (?, 0, datetime('now'))", (c,))
            folders[c] = cur.lastrowid

    before = cur.execute("SELECT COUNT(*) FROM AIResponses").fetchone()[0]
    inserted = 0
    for r in kept:
        fid = folders[r["course"]]
        cur.execute(
            "INSERT INTO AIResponses (Question, Answer, Options, QuestionType, IsAi, IsPendingCorrection, "
            "CreateTime, FolderId, FolderName) VALUES (?, ?, ?, ?, 0, 0, datetime('now'), ?, ?)",
            (r["question"], r["answer"], r["options"], r["qtype"], fid, r["course"]),
        )
        inserted += 1
    conn.commit()

    after = cur.execute("SELECT COUNT(*) FROM AIResponses").fetchone()[0]
    print("\n写入完成: 前 %d 条 → 后 %d 条, 本次插入 %d 条" % (before, after, inserted))
    print("文件夹:", cur.execute("SELECT Id, Name, ParentId FROM Folders ORDER BY Id").fetchall())
    conn.close()


if __name__ == "__main__":
    main()
